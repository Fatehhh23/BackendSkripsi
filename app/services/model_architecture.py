"""
Program 4: PI-ResNet50 Architecture
=====================================
Physics-Informed ResNet-50 U-Net untuk prediksi kedalaman inundasi
dan zonasi bahaya tsunami di Selat Sunda.

Menggantikan PI-MMViT (ViT bottleneck) dengan:
  ┌─────────────────────────────────────────────────────────────┐
  │  ENCODER : ResNet-50 pretrained (ImageNet) — 5 level skip   │
  │  FUSION  : FiLM (Feature-wise Linear Modulation) di         │
  │            bottleneck layer4 → fault params memodulasi      │
  │            feature map secara channel-wise affine           │
  │  DECODER : U-Net style ConvTranspose2d + skip connections   │
  │  HEAD    : (1) Segmentasi 3-kelas, (2) Regresi kedalaman    │
  └─────────────────────────────────────────────────────────────┘

Alasan penggantian ViT → ResNet-50:
  - Transfer learning: bobot pretrained ImageNet membawa inductive bias
    edge/gradient detector yang berguna untuk DEM (slope, kontur)
  - Parameter lebih efisien: ~35M vs ~55M (PI-MMViT dengan ViT)
  - Lebih stabil saat dataset kecil (5000 sampel sintetis)
  - FiLM lebih ringan dan ekspresif dari cross-attention untuk fusi tabular

Arsitektur detail (input 256x256):
  ENCODER (ResNet-50):
    stem  : Conv7x7(s2)+BN+ReLU       → e0:   64 @ 128x128
            MaxPool(s2)                →        64 @  64x64
    layer1: 3x Bottleneck             → e1:  256 @  64x64
    layer2: 4x Bottleneck             → e2:  512 @  32x32
    layer3: 6x Bottleneck             → e3: 1024 @  16x16
    layer4: 3x Bottleneck             → e4: 2048 @   8x8  <- bottleneck

  FiLM Fusion:
    fault(9) -> MLP -> (gamma, beta) in R^2048
    e4_fused = (1+gamma) * e4 + beta

  DECODER (U-Net):
    up4 + cat(e3): DoubleConv(3072 -> 512)  @ 16x16
    up3 + cat(e2): DoubleConv(1024 -> 256)  @ 32x32
    up2 + cat(e1): DoubleConv( 512 -> 128)  @ 64x64
    up1 + cat(e0): DoubleConv( 192 ->  64)  @ 128x128
    up0           : DoubleConv(  64 ->  64)  @ 256x256

  HEADS:
    seg_head   : Conv1x1(64->3)   -> logit zonasi (B,3,256,256)
    depth_head : Conv3x3+ReLU     -> kedalaman (m) (B,256,256)

Referensi:
  - He K. et al. (2016) Deep Residual Learning for Image Recognition.
    CVPR 2016. doi: 10.1109/CVPR.2016.90
  - Ronneberger O. et al. (2015) U-Net: Convolutional Networks for
    Biomedical Image Segmentation. MICCAI 2015.
  - Perez E. et al. (2018) FiLM: Visual Reasoning with a General
    Conditioning Layer. AAAI 2018. arXiv:1709.07871
"""

import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import resnet50, ResNet50_Weights


# ============================================================
# 1. BLOK DECODER: DoubleConv
# ============================================================
class DoubleConv(nn.Module):
    """
    Blok konvolusi ganda untuk decoder U-Net:
        Conv3x3 -> BN -> GELU -> Dropout2D -> Conv3x3 -> BN -> GELU

    Menggunakan GELU (bukan ReLU) karena lebih halus di near-zero region,
    penting untuk prediksi kedalaman inundasi kecil mendekati 0 m.

    Parameters
    ----------
    in_ch  : int   -- jumlah channel input
    out_ch : int   -- jumlah channel output
    drop_p : float -- probabilitas Dropout2d (default 0.1)
    """
    def __init__(self, in_ch: int, out_ch: int, drop_p: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Dropout2d(p=drop_p),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ============================================================
# 2. FiLM FUSION LAYER
# ============================================================
class FiLMFusion(nn.Module):
    """
    Feature-wise Linear Modulation (FiLM) untuk kondisioning fitur CNN
    berdasarkan parameter gempa tabular (Perez et al. 2018).

    Mekanisme:
        fault -> MLP -> [gamma, beta] in R^(2 x C)
        output = (1 + gamma) * features + beta

    Menggunakan (1 + gamma) bukan gamma agar inisialisasi identitas:
    saat gamma=0, beta=0: output = features (tidak ada perubahan awal).
    Hal ini membuat pelatihan lebih stabil di epoch pertama.

    Kenapa FiLM lebih baik dari simple concat di bottleneck?
      - Concat: menambah channel -> decoder bertambah besar, lebih lambat
      - FiLM: memodulasi secara multiplicative + additive -> lebih ekspresif
        dengan parameter jauh lebih sedikit
      - Terbukti efektif untuk multi-modal fusion (Perez et al. 2018)

    Parameters
    ----------
    fault_dim : int   -- dimensi vektor parameter gempa (default 9)
    feat_ch   : int   -- jumlah channel feature map bottleneck (default 2048)
    hidden    : int   -- hidden size MLP (default 512)
    drop_p    : float -- dropout di MLP (default 0.1)
    """
    def __init__(self, fault_dim: int = 9, feat_ch: int = 2048,
                 hidden: int = 512, drop_p: float = 0.1):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(fault_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Dropout(p=drop_p),
            nn.Linear(hidden, feat_ch * 2),   # output: gamma (C) ++ beta (C)
        )
        # Inisialisasi output layer ke nol -> identitas saat awal training
        nn.init.zeros_(self.mlp[-1].weight)
        nn.init.zeros_(self.mlp[-1].bias)

    def forward(self, features: torch.Tensor,
                fault: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        features : (B, C, H, W) -- feature map bottleneck dari layer4
        fault    : (B, fault_dim) -- parameter gempa ternorm [0,1]

        Returns
        -------
        modulated : (B, C, H, W) -- feature map setelah FiLM conditioning
        """
        params = self.mlp(fault)                # (B, 2C)
        gamma, beta = params.chunk(2, dim=1)    # masing-masing (B, C)
        gamma = gamma.unsqueeze(-1).unsqueeze(-1)   # (B, C, 1, 1)
        beta  = beta.unsqueeze(-1).unsqueeze(-1)    # (B, C, 1, 1)
        return (1.0 + gamma) * features + beta


# ============================================================
# 3. ARSITEKTUR UTAMA: PI-ResNet50
# ============================================================

class LightFiLM(nn.Module):
    def __init__(self, fault_dim: int = 9, feat_ch: int = 512):
        super().__init__()
        hidden = max(64, feat_ch // 8)  
        self.mlp = nn.Sequential(
            nn.Linear(fault_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, feat_ch * 2),
        )
        nn.init.zeros_(self.mlp[-1].weight)
        nn.init.zeros_(self.mlp[-1].bias)

    def forward(self, features: torch.Tensor, fault: torch.Tensor) -> torch.Tensor:
        params      = self.mlp(fault)
        gamma, beta = params.chunk(2, dim=1)
        gamma = gamma.unsqueeze(-1).unsqueeze(-1)
        beta  = beta.unsqueeze(-1).unsqueeze(-1)
        return (1.0 + gamma) * features + beta


class PIResNet50(nn.Module):
    def __init__(
        self,
        fault_dim       : int   = 9,
        num_classes     : int   = 3,
        pretrained      : bool  = True,
        freeze_backbone : bool  = False,
        drop_p          : float = 0.1,
        film_hidden     : int   = 512,
        use_light_film  : bool  = True,
        in_channels     : int   = 10,   # SINKRONISASI: Input 10 Channel
    ):
        super().__init__()
        self.use_light_film = use_light_film

        weights  = ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        backbone = resnet50(weights=weights)

        # Adaptasi Conv1 untuk menerima input 10 Channel
        adapted_conv1 = nn.Conv2d(
            in_channels, 64, kernel_size=7, stride=2, padding=3, bias=False
        )
        if pretrained:
            with torch.no_grad():
                rgb_mean = backbone.conv1.weight.mean(dim=1, keepdim=True)
                adapted_conv1.weight.copy_(rgb_mean.expand_as(adapted_conv1.weight))
                jitter = torch.randn_like(adapted_conv1.weight) * 0.01 * rgb_mean.std()
                adapted_conv1.weight.add_(jitter)

        self.stem_conv = nn.Sequential(
            adapted_conv1,
            backbone.bn1,
            backbone.relu,
        )
        self.stem_pool = backbone.maxpool

        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4

        if freeze_backbone:
            self._freeze_layers([self.stem_conv, self.stem_pool,
                                  self.layer1, self.layer2])

        self.film = FiLMFusion(
            fault_dim = fault_dim,
            feat_ch   = 2048,
            hidden    = film_hidden,
            drop_p    = drop_p,
        )

        self.up4  = nn.ConvTranspose2d(2048, 1024, 2, stride=2)
        self.dec4 = DoubleConv(1024 + 1024, 512, drop_p)

        self.up3  = nn.ConvTranspose2d(512, 512, 2, stride=2)
        self.dec3 = DoubleConv(512 + 512, 256, drop_p)

        self.up2  = nn.ConvTranspose2d(256, 256, 2, stride=2)
        self.dec2 = DoubleConv(256 + 256, 128, drop_p)

        self.up1  = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec1 = DoubleConv(64 + 64, 64, drop_p)

        self.up0  = nn.ConvTranspose2d(64, 64, 2, stride=2)
        self.dec0 = DoubleConv(64, 64, drop_p)

        if use_light_film:
            self.lfilm4 = LightFiLM(fault_dim, 512)
            self.lfilm3 = LightFiLM(fault_dim, 256)
            self.lfilm2 = LightFiLM(fault_dim, 128)

        self.pre_head_norm = nn.GroupNorm(num_groups=8, num_channels=64)

        self.seg_head = nn.Conv2d(64, num_classes, kernel_size=1)

        self.depth_head = nn.Sequential(
            nn.Conv2d(64, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.GELU(),
            nn.Conv2d(32, 1, kernel_size=1),
        )
        self._depth_softplus_beta = 5.0

        self.ssh_head = nn.Sequential(
            nn.Conv2d(64, 16, kernel_size=1),
            nn.GELU(),
            nn.Conv2d(16, 1, kernel_size=1),
        )

        self._init_decoder_weights()

    @staticmethod
    def _freeze_layers(modules: list) -> None:
        for mod in modules:
            for param in mod.parameters():
                param.requires_grad = False

    def unfreeze_backbone(self) -> None:
        for param in self.parameters():
            param.requires_grad = True

    def _init_decoder_weights(self) -> None:
        decoder_mods = [
            self.film, self.up4, self.dec4, self.up3, self.dec3,
            self.up2, self.dec2, self.up1, self.dec1, self.up0, self.dec0,
            self.pre_head_norm, self.seg_head, self.depth_head, self.ssh_head,
        ]
        if self.use_light_film:
            decoder_mods += [self.lfilm4, self.lfilm3, self.lfilm2]

        for mod in decoder_mods:
            for m in mod.modules():
                if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)
                elif isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)
                elif isinstance(m, (nn.BatchNorm2d, nn.GroupNorm, nn.LayerNorm)):
                    nn.init.ones_(m.weight)
                    nn.init.zeros_(m.bias)

    def get_param_groups(self, base_lr: float) -> list:
        backbone_params = (
            list(self.stem_conv.parameters()) + list(self.stem_pool.parameters()) +
            list(self.layer1.parameters()) + list(self.layer2.parameters()) +
            list(self.layer3.parameters()) + list(self.layer4.parameters())
        )
        bb_ids = {id(p) for p in backbone_params}
        decoder_params = [p for p in self.parameters() if id(p) not in bb_ids]
        return [
            {'params': backbone_params, 'lr': base_lr * 0.1,  'name': 'backbone'},
            {'params': decoder_params,  'lr': base_lr * 1.0,  'name': 'decoder'},
        ]

    def forward(self, dem: torch.Tensor, fault: torch.Tensor) -> tuple:
        e0 = self.stem_conv(dem)           
        x  = self.stem_pool(e0)            
        e1 = self.layer1(x)                
        e2 = self.layer2(e1)               
        e3 = self.layer3(e2)               
        e4 = self.layer4(e3)               

        e4 = self.film(e4, fault)          

        x = self.dec4(torch.cat([self.up4(e4), e3], dim=1))
        if self.use_light_film: x = self.lfilm4(x, fault)

        x = self.dec3(torch.cat([self.up3(x), e2], dim=1))
        if self.use_light_film: x = self.lfilm3(x, fault)

        x = self.dec2(torch.cat([self.up2(x), e1], dim=1))
        if self.use_light_film: x = self.lfilm2(x, fault)

        x = self.dec1(torch.cat([self.up1(x), e0], dim=1))
        x = self.dec0(self.up0(x))

        x = self.pre_head_norm(x)
        out_seg = self.seg_head(x) 
        
        depth_raw = self.depth_head(x).squeeze(1) 
        out_depth = F.softplus(depth_raw, beta=self._depth_softplus_beta) 

        out_ssh = self.ssh_head(x).squeeze(1)

        return out_seg, out_depth, out_ssh

# ============================================================
# TEST & BENCHMARKING
# ============================================================
if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"{'='*60}")
    print(f"  PI-ResNet50 — Architecture Test")
    print(f"{'='*60}")
    print(f"  Device: {device}")

    model = PIResNet50(pretrained=True, freeze_backbone=False).to(device)

    total_p     = sum(p.numel() for p in model.parameters())
    trainable_p = sum(p.numel() for p in model.parameters() if p.requires_grad)
    backbone_p  = sum(
        p.numel() for n, p in model.named_parameters()
        if any(k in n for k in ['stem_conv', 'stem_pool',
                                 'layer1', 'layer2', 'layer3', 'layer4'])
    )
    decoder_p = total_p - backbone_p

    print(f"\n  PARAMETER COUNT:")
    print(f"    Total           : {total_p:>12,}")
    print(f"    Trainable       : {trainable_p:>12,}")
    print(f"    Backbone (R50)  : {backbone_p:>12,}  ({backbone_p/total_p*100:.1f}%)")
    print(f"    Decoder + FiLM  : {decoder_p:>12,}  ({decoder_p/total_p*100:.1f}%)")

    # ── Forward pass ──────────────────────────────────────────────────────
    dummy_dem   = torch.randn(2, 3, 256, 256).to(device)
    dummy_fault = torch.rand(2, 9).to(device)

    model.eval()
    with torch.no_grad():
        t0 = time.time()
        seg, depth = model(dummy_dem, dummy_fault)
        t1 = time.time()

    print(f"\n  FORWARD PASS (batch=2):")
    print(f"    dem   in : {list(dummy_dem.shape)}")
    print(f"    fault in : {list(dummy_fault.shape)}")
    print(f"    seg  out : {list(seg.shape)}")
    print(f"    depth out: {list(depth.shape)}")
    print(f"    Latency  : {(t1-t0)*1000:.1f} ms")

    assert seg.shape   == (2, 3, 256, 256)
    assert depth.shape == (2, 256, 256)
    assert depth.min() >= 0.0
    assert not torch.isnan(seg).any()
    assert not torch.isnan(depth).any()
    print(f"    depth min/max: {depth.min():.4f} / {depth.max():.4f} m")
    print(f"    All assertions: PASSED ✓")

    # ── Differential LR groups ────────────────────────────────────────────
    print(f"\n  DIFFERENTIAL LR GROUPS (base_lr=2e-4):")
    for g in model.get_param_groups(2e-4):
        n = sum(p.numel() for p in g['params'])
        print(f"    [{g['name']:8s}] lr={g['lr']:.1e}  params={n:,}")

    # ── FiLM sensitivity test ─────────────────────────────────────────────
    dem1   = torch.randn(1, 3, 256, 256).to(device)
    faultA = torch.rand(1, 9).to(device)
    faultB = torch.rand(1, 9).to(device)
    with torch.no_grad():
        _, dA = model(dem1, faultA)
        _, dB = model(dem1, faultB)
    diff = (dA - dB).abs().mean().item()
    print(f"\n  FiLM SENSITIVITY (DEM sama, fault berbeda):")
    status = "PASS ✓" if diff > 1e-5 else "FAIL ✗ — fault tidak berpengaruh!"
    print(f"    mean |depth_A - depth_B| = {diff:.6f}  [{status}]")

    print(f"\n{'='*60}")
    print(f"  PI-ResNet50 siap digunakan di _05_train_eval_export.py")
    print(f"{'='*60}")



"""
Program 4: PI-MMViT Architecture
=================================
Physics-Informed Multi-Modal Vision Transformer untuk prediksi
kedalaman inundasi dan zonasi bahaya tsunami.

Arsitektur Hybrid CNN-Transformer (U-Net Backbone + ViT Bottleneck):
  - Encoder CNN : Ekstraksi fitur spasial lokal dari DEM
  - Fault Encoder: Proyeksi parameter gempa → fault token
  - ViT Bottleneck: Cross-modal attention antara fitur spasial dan seismik
  - Decoder CNN : Upsampling dengan skip connections (U-Net style)
  - Multi-Task   : (1) Segmentasi zonasi 3-kelas, (2) Regresi kedalaman

Perbaikan vs versi lama:
  [IMPROVE #1] Dropout (p=0.1) ditambahkan di setiap blok encoder
               untuk regularisasi dan mengurangi overfitting
  [IMPROVE #2] Positional Encoding ditambahkan ke sekuens Transformer
               agar informasi posisi spasial tidak hilang setelah flatten
  [IMPROVE #3] Layer Normalization tambahan sebelum head prediksi
  [IMPROVE #4] Fault encoder dilengkapi Dropout untuk regularisasi tabular
  [IMPROVE #5] Docstring lengkap dengan dimensi tensor di setiap tahap
  [IMPROVE #6] Test forward pass lebih komprehensif di __main__

Referensi:
  - Dosovitskiy et al. (2021) An Image is Worth 16x16 Words. ICLR 2021.
  - Ronneberger et al. (2015) U-Net. MICCAI 2015.
  - Vaswani et al. (2017) Attention Is All You Need. NeurIPS 2017.
"""


# ============================================================
# 1b. BLOK DASAR PI-MMViT (DoubleConv reuse dari atas)
# ============================================================
# DoubleConv sudah didefinisikan di atas (baris ~67) dan dipakai bersama
# oleh PI-ResNet50 maupun PI-MMViT. Tidak perlu didefinisikan ulang.



# ============================================================
# 1. CNN STEM
# ============================================================

class CNNStem(nn.Module):
    def __init__(self, in_channels: int = 10):
        super().__init__()
        self.enc1 = self._block(in_channels, 32, stride=1)   # (B, 32, 256, 256)
        self.enc2 = self._block(32, 64, stride=2)            # (B, 64, 128, 128)
        self.enc3 = self._block(64, 128, stride=2)           # (B, 128, 64, 64)
        self.enc4 = self._block(128, 256, stride=2)          # (B, 256, 32, 32)
        self.enc5 = self._block(256, 256, stride=2)          # (B, 256, 16, 16)

    @staticmethod
    def _block(in_ch: int, out_ch: int, stride: int = 1) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor):
        e1 = self.enc1(x)  
        e2 = self.enc2(e1) 
        e3 = self.enc3(e2) 
        e4 = self.enc4(e3) 
        e5 = self.enc5(e4) 
        return e1, e2, e3, e4, e5

# ============================================================
# 2. PATCH EMBEDDING
# ============================================================

class PatchEmbed(nn.Module):
    def __init__(self, in_channels: int = 10, patch_size: int = 16, d_model: int = 256):
        super().__init__()
        self.patch_size = patch_size
        self.proj = nn.Conv2d(in_channels, d_model, kernel_size=patch_size, stride=patch_size, bias=False)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.proj(x)        
        x = x.flatten(2)        
        x = x.transpose(1, 2)   
        return self.norm(x)

# ============================================================
# 3. LEARNABLE 2D POSITIONAL ENCODING
# ============================================================

class LearnablePositionalEncoding2D(nn.Module):
    def __init__(self, d_model: int, grid_size: int = 16, dropout_p: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout_p)
        n_spatial = grid_size * grid_size        
        
        self.pe_spatial = nn.Parameter(torch.zeros(1, n_spatial, d_model))
        self.pe_fault = nn.Parameter(torch.zeros(1, 1, d_model))

        nn.init.trunc_normal_(self.pe_spatial, std=0.02)
        nn.init.trunc_normal_(self.pe_fault, std=0.02)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        pe = torch.cat([self.pe_fault, self.pe_spatial], dim=1)  
        return self.dropout(tokens + pe)

# ============================================================
# 4. SKIP FUSION DECODER BLOCK
# ============================================================

class SkipFusionBlock(nn.Module):
    def __init__(self, in_ch: int, skip_ch: int, out_ch: int, dropout_p: float = 0.0):
        super().__init__()
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        fused_ch = in_ch + skip_ch

        layers = [
            nn.Conv2d(fused_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        ]
        if dropout_p > 0:
            layers.append(nn.Dropout2d(p=dropout_p))
        layers += [
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.GELU(),
        ]
        self.conv = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)                                  
        x = torch.cat([x, skip], dim=1)                 
        return self.conv(x)                             

# ============================================================
# 5. ARSITEKTUR UTAMA: PI-MMViT
# ============================================================

class PIMMViT(nn.Module):
    def __init__(
        self,
        dem_channels : int   = 10,  # <-- Default diubah ke 10
        fault_dim    : int   = 9,
        num_classes  : int   = 3,
        patch_size   : int   = 16,
        img_size     : int   = 256,
        d_model      : int   = 256,
        nhead        : int   = 8,
        num_layers   : int   = 6,
        dropout_p    : float = 0.1,
    ):
        super().__init__()
        self.patch_size  = patch_size
        self.img_size    = img_size
        self.grid_size   = img_size // patch_size    
        self.num_patches = self.grid_size ** 2       

        self.cnn_stem = CNNStem(in_channels=dem_channels)
        self.patch_embed = PatchEmbed(in_channels=dem_channels, patch_size=patch_size, d_model=d_model)

        self.fault_proj = nn.Sequential(
            nn.Linear(fault_dim, d_model // 2),
            nn.LayerNorm(d_model // 2),
            nn.GELU(),
            nn.Dropout(p=dropout_p),
            nn.Linear(d_model // 2, d_model),
            nn.LayerNorm(d_model),
        )

        self.pos_enc = LearnablePositionalEncoding2D(d_model=d_model, grid_size=self.grid_size, dropout_p=dropout_p)

        enc_layer = nn.TransformerEncoderLayer(
            d_model         = d_model,
            nhead           = nhead,
            dim_feedforward = d_model * 4,      
            dropout         = dropout_p,
            batch_first     = True,
            activation      = 'gelu',
            norm_first      = True,             
        )
        self.transformer = nn.TransformerEncoder(encoder_layer=enc_layer, num_layers=num_layers, enable_nested_tensor=False)

        self.bottleneck_fusion = nn.Sequential(
            nn.Conv2d(d_model + 256, d_model, kernel_size=1, bias=False),
            nn.BatchNorm2d(d_model),
            nn.GELU(),
        )

        self.dec4 = SkipFusionBlock(d_model, 256, 256, dropout_p=0.10)
        self.dec3 = SkipFusionBlock(256, 128, 128, dropout_p=0.10)
        self.dec2 = SkipFusionBlock(128, 64, 64,  dropout_p=0.05)
        self.dec1 = SkipFusionBlock(64, 32, 32,  dropout_p=0.00)

        self.pre_head_norm = nn.GroupNorm(8, 32)    

        self.seg_head = nn.Conv2d(32, num_classes, kernel_size=1)
        self.depth_head = nn.Sequential(
            nn.Conv2d(32, 16, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(16),
            nn.GELU(),
            nn.Conv2d(16, 1, kernel_size=1),
            nn.Softplus(beta=1, threshold=20),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, (nn.BatchNorm2d, nn.LayerNorm, nn.GroupNorm)):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, dem: torch.Tensor, fault: torch.Tensor):
        B = dem.shape[0]

        e1, e2, e3, e4, e5 = self.cnn_stem(dem)
        patch_tokens = self.patch_embed(dem)                   
        fault_token = self.fault_proj(fault).unsqueeze(1)      
        
        tokens = torch.cat([fault_token, patch_tokens], dim=1) 
        tokens = self.pos_enc(tokens)

        out_tokens = self.transformer(tokens)                  
        spatial_tokens = out_tokens[:, 1:, :]                  
        vit_feat = (spatial_tokens.transpose(1, 2).view(B, -1, self.grid_size, self.grid_size)) 

        fused = torch.cat([vit_feat, e5], dim=1)              
        x = self.bottleneck_fusion(fused)                      

        x = self.dec4(x, e4)   
        x = self.dec3(x, e3)   
        x = self.dec2(x, e2)   
        x = self.dec1(x, e1)   

        x = self.pre_head_norm(x)

        out_seg   = self.seg_head(x)                           
        out_depth = self.depth_head(x).squeeze(1)              

        return out_seg, out_depth

# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Device: {device}")

    model = PIMMViT().to(device)

    # Hitung jumlah parameter
    total_params     = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[*] Total Parameter     : {total_params:,}")
    print(f"[*] Trainable Parameter : {trainable_params:,}")

    # Forward pass test
    dummy_dem   = torch.randn(2, 3, 256, 256).to(device)
    dummy_fault = torch.randn(2, 9).to(device)

    model.eval()
    with torch.no_grad():
        pred_seg, pred_depth = model(dummy_dem, dummy_fault)

    print(f"\n✅ FORWARD PASS BERHASIL!")
    print(f"   Input DEM         : {list(dummy_dem.shape)}")
    print(f"   Input Fault       : {list(dummy_fault.shape)}")
    print(f"   Output Seg Logits : {list(pred_seg.shape)}  (B, 3, H, W)")
    print(f"   Output Depth      : {list(pred_depth.shape)}  (B, H, W)")

    # Verifikasi output depth ≥ 0 (karena ada ReLU di depth_head)
    assert pred_depth.min() >= 0.0, "Depth output negatif! Cek ReLU di depth_head."
    print(f"   Depth min/max     : {pred_depth.min():.4f} / {pred_depth.max():.4f} m ✓")

    # Verifikasi channel seg = 3
    assert pred_seg.shape[1] == 3, "Output seg bukan 3 kelas!"
    print(f"   Seg classes       : {pred_seg.shape[1]} (Aman/Waspada/Bahaya) ✓")
