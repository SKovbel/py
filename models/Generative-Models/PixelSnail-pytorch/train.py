import os
import time
import torch
import torch.nn as nn
import torchvision

from tqdm import tqdm
from model import PixelSnail
from PIL import Image, ImageOps

TRY_CUDA = True
MODEL_SAVING = True
NB_EPOCHS = 200
BATCH_SIZE = 32
DIR = f'{os.path.dirname(os.path.abspath(__file__))}/../../../tmp/gems'

class ResizeWithPadding:
    def __init__(self, size, fill=(0, 0, 0)):
        self.size = size 
        self.fill = fill

    def __call__(self, image):
        image.thumbnail(self.size, Image.BICUBIC)
        new_image = Image.new("RGB", self.size, self.fill)
        new_image.paste(image, ((self.size[0] - image.width) // 2, (self.size[1] - image.height) // 2))
        return new_image

transform_images = torchvision.transforms.Compose([
    ResizeWithPadding((128, 128)),
    torchvision.transforms.ToTensor(),
])

device = torch.device('cuda' if TRY_CUDA and torch.cuda.is_available() else 'cpu')
print(f"> Using device {device}")

print(f"> Instantiating PixelSnail")
# model = PixelSnail([28, 28], 256, 32, 5, 3, 2, 16, nb_out_res_block=2).to(device)
model = PixelSnail([128, 128], 256, 32, 5, 3, 2, 16, nb_cond_res_block=2, cond_res_channel=16, nb_out_res_block=2).to(device)
print(f"> Number of parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}\n")

print("> Loading dataset")
#train_dataset = torchvision.datasets.MNIST('data', train=True, download=True, transform=torchvision.transforms.ToTensor())
#test_dataset = torchvision.datasets.MNIST('data', train=False, download=True, transform=torchvision.transforms.ToTensor())
train_dataset = torchvision.datasets.ImageFolder(root=f'{DIR}/train', transform=transform_images)
test_dataset = torchvision.datasets.ImageFolder(root=f'{DIR}/test', transform=transform_images)

train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

optim = torch.optim.Adam(model.parameters(), lr=0.001)
crit = nn.CrossEntropyLoss()

save_id = int(time.time())

for ei in range(NB_EPOCHS):
    print(f"\n> Epoch {ei+1}/{NB_EPOCHS}")
    train_loss = 0.0
    eval_loss = 0.0

    model.train()
    for x, c in tqdm(train_loader):
        optim.zero_grad()
        x = (x*255).long().squeeze().to(device)
        c = c.view(-1,1,1).expand(-1,7,7).to(device)

        pred, _, __ = model(x, c=c)
        loss = crit(pred.view(BATCH_SIZE, 256, -1), x.view(BATCH_SIZE, -1))
        train_loss += loss.item()

        loss.backward()
        optim.step()

    model.eval()
    with torch.no_grad():
        for i, (x, c) in enumerate(tqdm(test_loader)):
            optim.zero_grad()
            x = (x*255).long().squeeze().to(device)
            c = c.view(-1,1,1).expand(-1,7,7).to(device)

            pred, _ = model(x, c=c)
            loss = crit(pred.view(BATCH_SIZE, 256, -1), x.view(BATCH_SIZE, -1))
            eval_loss += loss.item()

            if i == 0:
                img = torch.cat([x, torch.argmax(pred, dim=1)], dim=0) / 255.
                torchvision.utils.save_image(img.unsqueeze(1), f"imgs/pixelcnn-{ei}.png")
    torch.save(model.state_dict(), f"checkpoints/{save_id}-{ei}-pixelcnn.pt")
    print(f"> Training Loss: {train_loss / len(train_loader)}")
    print(f"> Evaluation Loss: {eval_loss / len(test_loader)}")
