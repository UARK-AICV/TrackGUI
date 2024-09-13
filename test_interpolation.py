import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF
import os 
import glob
from sklearn import preprocessing
import scipy 
import sys 
import scipy.spatial
from scipy import interpolate
import cv2

def cvt_xyxy2xywh(old_bboxes):
    new_bboxes = np.zeros(old_bboxes.shape)
    new_bboxes[:,0] = (old_bboxes[:,0]+old_bboxes[:,2])/2
    new_bboxes[:,1] = (old_bboxes[:,1]+old_bboxes[:,3])/2
    new_bboxes[:,2] = old_bboxes[:,2] - old_bboxes[:,0]
    new_bboxes[:,3] = old_bboxes[:,3] - old_bboxes[:,1]
    return new_bboxes

def cvt_xywh2xyxy(old_bboxes):
    new_bboxes = np.zeros(old_bboxes.shape)
    dw = old_bboxes[:,2]/2
    dh = old_bboxes[:,3]/2
    new_bboxes[:,0] = old_bboxes[:,0] - dw
    new_bboxes[:,1] = old_bboxes[:,1] - dh
    new_bboxes[:,2] = old_bboxes[:,0] + dw
    new_bboxes[:,3] = old_bboxes[:,1] + dh
    return new_bboxes


s_e = [130,330]
id = 7
anno_folder = "/home/tpware/Downloads/dl_asgn1/frame_multiviews/anno2"
txt_paths = sorted(glob.glob(os.path.join(anno_folder,"*.txt")),key=lambda x:int(x.split('/')[-1].split('.txt')[0]))

img_folder = "/home/tpware/Downloads/dl_asgn1/frame_multiviews/moving_view2"
img_paths = sorted(glob.glob(os.path.join(img_folder,"*.jpg")),key=lambda x:int(x.split('/')[-1].split('.jpg')[0]))

save_folder = "/home/tpware/projects/Tracking_Tool/data/interpolated_data/"

xyxy_bboxes = []
for jdx in range(len(txt_paths)):
    txt_p = txt_paths[jdx]
    if int(os.path.basename(txt_p).split('.')[0]) >= s_e[0] and int(os.path.basename(txt_p).split('.')[0]) <= s_e[1]:
        with open(txt_p) as f:
            lines = [line.rstrip('\n') for line in f]
        for kdx in range(len(lines)):
            if ' 7 ' in lines[kdx]:
                xyxy_bboxes.append(lines[kdx].split(' ')[2:])

xyxy_bboxes = np.array(xyxy_bboxes).astype(int)
xywh_bboxes = cvt_xyxy2xywh(xyxy_bboxes)

img_indices = np.linspace(0,xywh_bboxes.shape[0]-1,num=10,dtype=int)



from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RationalQuadratic 


# interpolated_data = []
# for jdx in range(4):
#     kernel = RationalQuadratic() 
#     gpr = GaussianProcessRegressor(kernel=kernel,random_state=0).fit(img_indices.reshape(-1,1), xywh_bboxes[:,jdx][img_indices])
#     print('Score:',gpr.score(img_indices.reshape(-1,1), xywh_bboxes[:,jdx][img_indices]))
#     interpolated_data.append(gpr.predict(np.arange(0,xywh_bboxes.shape[0]).reshape(-1,1), return_std=False))

# # import ipdb;ipdb.set_trace()
# interpolated_data = np.stack(interpolated_data,axis=1)
# cvt_interpolated_data = cvt_xywh2xyxy(interpolated_data).astype(int)

# cnt = 0
# for jdx in range(len(txt_paths)):
#     img_p = img_paths[jdx]
#     if int(os.path.basename(img_p).split('.')[0]) >= s_e[0] and int(os.path.basename(img_p).split('.')[0]) <= s_e[1]:
#         img = cv2.imread(img_p)
#         box = cvt_interpolated_data[cnt]
#         cv2.rectangle(img,(box[0],box[1]),(box[2],box[3]),(255,0,0),2)
#         cv2.imwrite(save_folder+os.path.basename(img_p),img)
#         cnt+=1


# dont work
"""
interpolated_data = [[],[],[],[]]
fdx_start = 0
for fdx in range(1,len(img_indices)):
    for jdx in range(4):
        kernel = RationalQuadratic() 
        # import ipdb; ipdb.set_trace()
        gpr = GaussianProcessRegressor(kernel=kernel,random_state=0).fit(np.array([0,int(img_indices[2]-img_indices[1])]).reshape(-1,1), xywh_bboxes[:,jdx][img_indices[fdx-1:fdx+1]])
        interpolated_data[jdx].extend(gpr.predict(np.arange(0,img_indices[fdx]-img_indices[fdx-1]).reshape(-1,1), return_std=False))
    fdx_start += 1



interpolated_data = np.stack(interpolated_data,axis=1)
cvt_interpolated_data = cvt_xywh2xyxy(interpolated_data).astype(int)

cnt = 0
for jdx in range(len(txt_paths)):
    img_p = img_paths[jdx]
    if int(os.path.basename(img_p).split('.')[0]) >= s_e[0] and int(os.path.basename(img_p).split('.')[0]) <= s_e[1]:
        img = cv2.imread(img_p)
        box = cvt_interpolated_data[cnt]
        cv2.rectangle(img,(box[0],box[1]),(box[2],box[3]),(0,255,0),2)
        cv2.imwrite(save_folder+os.path.basename(img_p),img)
        cnt+=1
"""



# interpolated_data = []
# for jdx in range(4):
#     f = interpolate.interp1d(img_indices, xywh_bboxes[:,jdx][img_indices])
#     filled_data = f(np.arange(0,xywh_bboxes.shape[0]))
#     interpolated_data.append(filled_data)

# interpolated_data = np.stack(interpolated_data,axis=1)
# cvt_interpolated_data = cvt_xywh2xyxy(interpolated_data).astype(int)

# cnt = 0
# for jdx in range(len(txt_paths)):
#     img_p = img_paths[jdx]
#     if int(os.path.basename(img_p).split('.')[0]) >= s_e[0] and int(os.path.basename(img_p).split('.')[0]) <= s_e[1]:
#         img = cv2.imread(img_p)
#         box = cvt_interpolated_data[cnt]
#         cv2.rectangle(img,(box[0],box[1]),(box[2],box[3]),(255,0,0),2)
#         cv2.imwrite(save_folder+os.path.basename(img_p),img)
#         cnt+=1







# import ipdb; ipdb.set_trace()
# img_indices = np.linspace(0,xyxy_bboxes.shape[0]-1,num=10,dtype=int)

# interpolated_data = []
# for jdx in range(4):
#     f = interpolate.interp1d(img_indices, xyxy_bboxes[:,jdx][img_indices])
#     filled_data = f(np.arange(0,xyxy_bboxes.shape[0]))
#     interpolated_data.append(filled_data)

# interpolated_data = np.stack(interpolated_data,axis=1).astype(int)

# cnt = 0
# for jdx in range(len(txt_paths)):
#     img_p = img_paths[jdx]
#     if int(os.path.basename(img_p).split('.')[0]) >= s_e[0] and int(os.path.basename(img_p).split('.')[0]) <= s_e[1]:
#         img = cv2.imread(img_p)
#         box = interpolated_data[cnt]
#         cv2.rectangle(img,(box[0],box[1]),(box[2],box[3]),(255,0,0),2)
#         cv2.imwrite(save_folder+os.path.basename(img_p),img)
#         cnt+=1


# import ipdb; ipdb.set_trace()


