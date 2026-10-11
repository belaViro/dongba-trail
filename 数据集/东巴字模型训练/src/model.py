"""Small CPU CNN; preserve 4x4 spatial layout for glyph identity."""

from torch import nn


class GlyphCNN(nn.Module):
    def __init__(self, classes):
        super().__init__()
        layers = []
        incoming = 1
        for outgoing in (24, 48, 80):
            layers.extend(
                [
                    nn.Conv2d(incoming, outgoing, 3, padding=1, bias=False),
                    nn.BatchNorm2d(outgoing),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                ]
            )
            incoming = outgoing
        self.features = nn.Sequential(*layers, nn.AdaptiveAvgPool2d((4, 4)))
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(80 * 4 * 4, 128),
            nn.LayerNorm(128),
            nn.LeakyReLU(negative_slope=0.1),
            nn.Dropout(0.2),
            nn.Linear(128, classes),
        )

    def forward(self, images):
        return self.classifier(self.features(images))
