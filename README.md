# GEES2Downloader
The GEES2Downloader, as its name suggests, is a simple downloader for S2 imagery from Google Earth Engine. 
The objective is to overcome the limitations imposed by GEE when downloading assets directly through HTTP protocol.

In these situations, the GEES2Downloader is able to subdivide the asset in smaller tiles and download them separately to recreate the original array (Figura 1).
The number of tiles is given automatically by the algorithm and the download occurs in parallel. 
![image](https://user-images.githubusercontent.com/19617404/143089632-a4323a8a-28b9-495e-ac7d-a8d5b89293f1.png)

# Instalation
The package can be installed directly from the github, using pip, like so:
`pip install git+https://github.com/cordmaur/GEES2Downloader.git@main`

Or cloning the project and installing in editor mode to access the code:
```
git clone https://github.com/cordmaur/GEES2Downloader.git
cd GEES2Downloader
pip install -e .
```

To check if it is correctly installed:
```
python
>>> import geeS2downloader
>>> geeS2downloader.__version__
'0.0.1'
```

# Usage
The usage is really simple. <br>
<b>Note:</b> img is a ee.Image and band is a string with the name of the band.
```
from geeS2downloader import GEES2Downloader

downloader = GEES2Downloader()
downloader.download(img, band)
```
![image](https://user-images.githubusercontent.com/19617404/143090216-b54e080d-6825-41af-9b60-de642f7aba77.png)


To visualize the the downloaded asset:
```
plt.imshow(downloader.array)
```
![image](https://user-images.githubusercontent.com/19617404/143090510-af656377-3e5a-463f-8391-fbb3e84278e2.png)


# Story
A story explaining in more details can be found here:




