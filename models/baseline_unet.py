"""Baseline U-Net for flood nowcasting: (B,30,110,160) -> (B,9,110,160)."""
import torch
import torch.nn as nn


def _blk(ci, co):
    return nn.Sequential(nn.Conv2d(ci, co, 3, padding=1), nn.ReLU(inplace=True),
                         nn.Conv2d(co, co, 3, padding=1), nn.ReLU(inplace=True))


class BaselineUNet(nn.Module):
    def __init__(self, in_ch=36, n_leads=9, base=32):
        super().__init__()
        self.e1 = _blk(in_ch, base)
        self.e2 = _blk(base, base * 2)
        self.e3 = _blk(base * 2, base * 4)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.d2 = _blk(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.d1 = _blk(base * 2, base)
        self.out = nn.Conv2d(base, n_leads, 1)

    def forward(self, x):
        import torch.nn.functional as F
        f1 = self.e1(x)
        f2 = self.e2(self.pool(f1))
        f3 = self.e3(self.pool(f2))
        u = self.up2(f3)
        dh, dw = f2.shape[2] - u.shape[2], f2.shape[3] - u.shape[3]
        u = F.pad(u, (0, dw, 0, dh))
        u = self.d2(torch.cat([u, f2], 1))
        v = self.up1(u)
        dh, dw = f1.shape[2] - v.shape[2], f1.shape[3] - v.shape[3]
        v = F.pad(v, (0, dw, 0, dh))
        v = self.d1(torch.cat([v, f1], 1))
        return self.out(v)

    def count_params(self):
        return sum(p.numel() for p in self.parameters())
