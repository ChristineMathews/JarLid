# -*- coding: utf-8 -*-
"""Untitled6.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1-QR4lRFtR8D2CWRq9nZL1z6Y_VWL43Px
"""

# In this example, we assume your images and CSV are located in /content/jarlids/
annots = '/content/jarlid/jarlids_annots.csv'
imagefiles = '/content/jarlid/'
dest = '/content/dest/'
results = '/content/results.txt'

# %% code
!git clone https://github.com/WongKinYiu/yolov7
!cd yolov7 && wget https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7.pt

!pip install imagesize ptitprince



!pip install matplotlib==3.4.3
!pip install seaborn==0.11.0 #upgrade both seaborn and matplotlib together to ensure compatibility.
import os
import re
import cv2
import json
import time
import shutil
import numpy as np
import pandas as pd
import imagesize
import ptitprince as pt
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patches as mpatches
import seaborn as sns
from distutils.dir_util import copy_tree
from shutil import copyfile
from PIL import Image, ImageDraw, ImageFont

# %% code
img = Image.open('/content/jarlid/p20.JPG')  # adjust filename as needed
draw = ImageDraw.Draw(img)
# Use a standard font available in Colab
font = ImageFont.load_default()
draw.text((8, 8), "Examples of jar lid damage", font=font, fill=(255, 255, 255))
img

# %% code
# Set indices for file splits (adjust these based on your dataset)
yfile = 'train.yaml'
tr_start = 1
tr_end = 125
va_start = 200
va_end = 239
te_start = 1
te_end = 6
va_te = 'val.txt'

class prepare_annotations():
    def __init__(self,
                 sourcedir=annots,
                 imagesdir=imagefiles,
                 destdir=dest,
                 namedir=dest,
                 yamlfile=yfile,
                 filename='im1.jpg',
                 trainstart=tr_start,
                 trainend=tr_end,
                 valstart=va_start,
                 valend=va_end,
                 teststart=te_start,
                 testend=te_end,
                 validationtest=va_te):
        self.sourcedir = sourcedir       # CSV with annotations
        self.imagesdir = imagesdir         # directory with images
        self.destdir = destdir             # destination directory for processed data
        self.namedir = namedir             # used in file paths in txt/yaml files
        self.yamlfile = yamlfile           # YAML filename for YOLOv7
        self.filename = filename
        self.trainstart = trainstart
        self.trainend = trainend
        self.valstart = valstart
        self.valend = valend
        self.teststart = teststart
        self.testend = testend
        self.validationtest = validationtest

    def isize(self, imagesdir, filename):
        w, h = imagesize.get(os.path.join(imagesdir, filename))
        return(w, h)

    def load_dataframe(self):
        dat = pd.read_csv(self.sourcedir)
        tr = ['p'+str(s)+'.JPG' for s in range(self.trainstart, self.trainend)]
        va = ['p'+str(s)+'.JPG' for s in range(self.valstart, self.valend)]
        te = ['t'+str(s)+'.JPG' for s in range(self.teststart, self.testend)]
        for i, j in zip(['train', 'val', 'test'], [tr, va, te]):
            dat.loc[dat['filename'].isin(j), 'dataset'] = i
        dat['region_attributes'] = dat['region_attributes'].replace({'{}': 'None'})
        dat = dat[~dat['region_attributes'].isin(['None'])].reset_index(drop=True)
        dat['category_names'] = dat['region_attributes'].apply(lambda x: str(list(eval(x).values())[0]))
        dat['category_codes'] = dat[['category_names']].apply(lambda x: pd.Categorical(x).codes)
        dat['image_width'] = dat['filename'].apply(lambda x: self.isize(self.imagesdir, x)[0])
        dat['image_height'] = dat['filename'].apply(lambda x: self.isize(self.imagesdir, x)[1])
        dat['x_min'] = dat['region_shape_attributes'].apply(lambda x: eval(x)['x'])
        dat['y_min'] = dat['region_shape_attributes'].apply(lambda x: eval(x)['y'])
        dat['bb_width'] = dat['region_shape_attributes'].apply(lambda x: eval(x)['width'])
        dat['bb_height'] = dat['region_shape_attributes'].apply(lambda x: eval(x)['height'])
        dat['n_x_center'] = (((dat['x_min'] + dat['bb_width']) + dat['x_min']) / 2) / dat['image_width']
        dat['n_y_center'] = (((dat['y_min'] + dat['bb_height']) + dat['y_min']) / 2) / dat['image_height']
        dat['n_width'] = dat['bb_width'] / dat['image_width']
        dat['n_height'] = dat['bb_height'] / dat['image_height']
        dat['color_cat'] = dat['category_names'].replace({'intact': 'green', 'damaged': 'red'})
        dat = dat.reset_index(drop=True)
        return(dat)

    def make_dirstructure(self):
        try:
            print('Preparing new directory tree...')
            os.makedirs(self.destdir, exist_ok=True)
            os.makedirs(os.path.join(self.destdir, 'images/'), exist_ok=True)
            os.makedirs(os.path.join(self.destdir, 'labels/'), exist_ok=True)
        except Exception as e:
            print('Error creating directories:', e)

        dat = self.load_dataframe()
        filenames = list(set(dat['filename']))
        for f in filenames:
            copyfile(os.path.join(self.imagesdir, f), os.path.join(self.destdir, 'images', f))
        print("Directory structure created and images copied.")

    def make_labels(self):
        dat = self.load_dataframe()
        print('Number of annotations:', len(dat))
        # Remove existing label files
        for i in list(set(dat['filename'])):
            try:
                os.remove(os.path.join(self.destdir, 'labels/', i[:-4]+'.txt'))
            except:
                pass

        print('Writing bounding box labels to:', os.path.join(self.destdir, 'labels/'))
        for i in range(len(dat)):
            try:
                with open(os.path.join(self.destdir, 'labels/', dat['filename'][i][:-4]+'.txt'), "a") as f:
                    print(dat['category_codes'][i], dat['n_x_center'][i], dat['n_y_center'][i],
                          dat['n_width'][i], dat['n_height'][i], file=f)
            except Exception as e:
                print('Error writing label for index', i, ':', e)

    def fixed_train_val_split(self):
        dat = self.load_dataframe()
        tr = ['p'+str(i)+'.JPG' for i in range(self.trainstart, self.trainend)]
        va = ['p'+str(i)+'.JPG' for i in range(self.valstart, self.valend)]
        te = ['t'+str(i)+'.JPG' for i in range(self.teststart, self.testend)]
        print('Splitting train, val, and test data...')
        for split in ['train.txt', 'val.txt', 'test.txt']:
            try:
                os.remove(os.path.join(self.destdir, split))
            except:
                pass

        with open(os.path.join(self.destdir, 'train.txt'), "a") as f:
            for img in tr:
                print(os.path.join(self.namedir, 'images', img), file=f)
        with open(os.path.join(self.destdir, 'val.txt'), "a") as f:
            for img in va:
                print(os.path.join(self.namedir, 'images', img), file=f)
        with open(os.path.join(self.destdir, 'test.txt'), "a") as f:
            for img in te:
                print(os.path.join(self.namedir, 'images', img), file=f)
        print("Data split files created.")

    def yaml_file(self):
        dat = self.load_dataframe()
        lb = list(sorted(set(dat['category_names'])))
        with open(os.path.join(self.destdir, self.yamlfile), "w") as f:
            print('names:', file=f)
            for i in lb:
                print('- ' + i, file=f)
            print('nc:', len(lb), file=f)
            print('train:', os.path.join(self.namedir, 'train.txt'), file=f)
            print('val:', os.path.join(self.namedir, self.validationtest), file=f)
        print("YAML file created.")

# Create a dataframe preview to check the annotations
df = prepare_annotations().load_dataframe()
print(df.head())

# %% code
def visualisation_annotations(dat, filedir, fname):
    im = Image.open(os.path.join(filedir, fname))
    fig, ax = plt.subplots(figsize=(14, 20))
    ax.imshow(im)
    ndat = dat[dat['filename'] == fname].reset_index()

    for i in range(len(ndat)):
        xmin = ndat['x_min'][i]
        ymin = ndat['y_min'][i]
        w = ndat['bb_width'][i]
        h = ndat['bb_height'][i]
        color = ndat['color_cat'][i]
        rect = patches.Rectangle((xmin, ymin), w, h, linewidth=2, edgecolor=color, facecolor='none')
        ax.add_patch(rect)

    # Create legend patches from the annotation colors
    mpatches_dat = pd.DataFrame(df[['category_names', 'color_cat']].value_counts().reset_index())
    patch1 = mpatches.Patch(color=mpatches_dat['color_cat'][0], label=mpatches_dat['category_names'][0])
    patch2 = mpatches.Patch(color=mpatches_dat['color_cat'][1], label=mpatches_dat['category_names'][1])
    ax.legend(handles=[patch1, patch2])
    plt.show()

# Visualize a sample image (adjust filename as needed)
visualisation_annotations(df, imagefiles, 'p15.JPG')

# %% code
def count_classes(dat, dataset):
    return(dat.loc[dat['dataset'] == dataset, "category_names"].value_counts())

print("Train class distribution:")
print(count_classes(df, "train"))
print("\nValidation class distribution:")
print(count_classes(df, "val"))

# %% code
pa = prepare_annotations()
pa.make_dirstructure()
pa.make_labels()
pa.fixed_train_val_split()
pa.yaml_file()

# Display the contents of the generated YAML file and one label file
!cat {os.path.join(dest, 'train.yaml')}
!cat {os.path.join(dest, 'labels', 'p1.txt')}

# %% code
import os
os.environ["WANDB_MODE"] = "offline"  # Set WANDB mode to offline

# Copy and modify the training configuration file
!cp 'yolov7/cfg/training/yolov7.yaml' '/content/yolov7_ad.yaml'
with open("/content/yolov7_ad.yaml", "r") as r:
    text = r.read().replace("nc: 80", "nc: 2")
with open("/content/yolov7_ad.yaml", "w") as w:
    w.write(text)
!head -5 '/content/yolov7_ad.yaml'

!cp 'yolov7/data/hyp.scratch.custom.yaml' '/content/hypownsettings.yaml'
with open("/content/hypownsettings.yaml", "r") as r:
    text = r.read().replace("mosaic: 1.0", "mosaic: 0.0").replace("flipud: 0.0", "flipud: 0.5").replace("scale: 0.5", "scale: 0.0")
with open("/content/hypownsettings.yaml", "w") as w:
    w.write(text)

!python yolov7/train.py --img 640 --batch 16 --epochs 100 --data /content/dest/train.yaml --hyp "/content/hypownsettings.yaml" --image-weights --cfg "/content/yolov7_ad.yaml" --weights '/content/yolov7/yolov7.pt' --cache

!cp '/content/runs/train/exp2/results.txt' '/content/results.txt'
!cp '/content/runs/train/exp2/results.png' '/content/results.png'
!cp '/content/runs/train/exp2/weights/best.pt' '/content/y7-prdef.pt'

# %% code
column_names = ['empty', 'x1', 'x2', 'Box', 'Objectness', 'Classification', 'x3', 'x4', 'x5',
                'Precision', 'Recall', 'mAP@0.5', 'mAP@0.5:0.95', 'val_Box', 'val_Obj', 'val_Class']

def text_spaces(inputtext, outputtext, colnames):
    dat = pd.DataFrame(columns=colnames)
    with open(inputtext) as f:
        lines = f.readlines()
    print('Number of lines in results.txt:', len(lines))
    for i in range(len(lines)):
        t1 = re.sub(' +', ', ', lines[i])
        t2 = re.sub('\n', '', t1)
        t3 = t2.split(",")
        dat.loc[i] = t3
    dat.to_csv(outputtext)
    return(dat)

df_lcurves = text_spaces(inputtext=results, outputtext='/content/results.csv', colnames=column_names)

plt.style.use('seaborn-whitegrid')
plt.figure(figsize=(14, 10))

line1 = ['Box', 'Objectness', 'Classification', 'Precision', 'mAP@0.5']
line2 = ['val_Box', 'val_Obj', 'val_Class', 'Recall', 'mAP@0.5:0.95']
col1 = ['blue', 'blue', 'blue', 'green', 'green']
col2 = ['red', 'red', 'red', 'orange', 'orange']
ylab = ['box_loss', 'obj_loss', 'cls_loss', 'precision/recall', 'mAP']

for i in range(len(line1)):
    ax = plt.subplot(3, 2, i+1)
    ax.plot(df_lcurves[line1[i]].astype(float), '.-', color=col1[i])
    ax.plot(df_lcurves[line2[i]].astype(float), '.-', color=col2[i])
    ax.set_ylabel(ylab[i])
    patch1 = mpatches.Patch(color=col1[i], label='train')
    patch2 = mpatches.Patch(color=col2[i], label='val')
    ax.legend(handles=[patch1, patch2])
plt.show()

# %% code
# Create a YAML file for the test set (if desired)
prepare_annotations(yamlfile='test_design.yaml', validationtest='test.txt').yaml_file()

!python yolov7/test.py --data {os.path.join(dest, 'test_design.yaml')} \
  --weights '/content/runs/train/exp2/weights/best.pt' --augment

# Display one of the resulting test images
Image.open('/content/runs/test/exp2/test_batch0_labels.jpg')

!python yolov7/detect.py --weights /content/runs/train/exp2/weights/best.pt --source /content/test1.jpg --img 640 --conf 0.1

from IPython.display import Image, display
display(Image(filename='/content/runs/detect/exp5/new.jpeg'))