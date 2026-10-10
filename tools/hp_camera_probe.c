/* V4L2 capability/frame-delivery test. Frame contents are discarded. */
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
int main(int argc,char**argv){
 if(argc!=2)return 2;int fd=open(argv[1],O_RDWR|O_NONBLOCK);if(fd<0){perror("open camera");return 1;}
 struct v4l2_capability c={0};if(ioctl(fd,VIDIOC_QUERYCAP,&c)){perror("QUERYCAP");return 1;}
 unsigned caps=c.capabilities&V4L2_CAP_DEVICE_CAPS?c.device_caps:c.capabilities;
 printf("device=%s driver=%.16s card=%.32s capabilities=%08x\n",argv[1],c.driver,c.card,caps);
 if(!(caps&V4L2_CAP_VIDEO_CAPTURE)||!(caps&V4L2_CAP_STREAMING)){puts("SKIP: not a streaming video-capture node");close(fd);return 0;}
 struct v4l2_format f={.type=V4L2_BUF_TYPE_VIDEO_CAPTURE};if(ioctl(fd,VIDIOC_G_FMT,&f)){perror("G_FMT");return 1;}
 printf("format width=%u height=%u fourcc=%c%c%c%c\n",f.fmt.pix.width,f.fmt.pix.height,f.fmt.pix.pixelformat&255,(f.fmt.pix.pixelformat>>8)&255,(f.fmt.pix.pixelformat>>16)&255,(f.fmt.pix.pixelformat>>24)&255);
 struct v4l2_requestbuffers req={.count=3,.type=V4L2_BUF_TYPE_VIDEO_CAPTURE,.memory=V4L2_MEMORY_MMAP};if(ioctl(fd,VIDIOC_REQBUFS,&req)){perror("REQBUFS");return 1;}if(req.count>8||!req.count)return 1;
 void*ptr[8];unsigned len[8];
 for(unsigned i=0;i<req.count;i++){struct v4l2_buffer b={.type=req.type,.memory=req.memory,.index=i};if(ioctl(fd,VIDIOC_QUERYBUF,&b)){perror("QUERYBUF");return 1;}len[i]=b.length;ptr[i]=mmap(NULL,b.length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,b.m.offset);if(ptr[i]==MAP_FAILED)return 1;if(ioctl(fd,VIDIOC_QBUF,&b)){perror("QBUF");return 1;}}
 enum v4l2_buf_type type=req.type;if(ioctl(fd,VIDIOC_STREAMON,&type)){perror("STREAMON");return 1;}
 unsigned frames=0,bytes=0;for(unsigned i=0;i<5;i++){struct pollfd p={fd,POLLIN,0};if(poll(&p,1,1500)<=0)break;struct v4l2_buffer b={.type=req.type,.memory=req.memory};if(ioctl(fd,VIDIOC_DQBUF,&b))break;frames++;bytes+=b.bytesused;if(ioctl(fd,VIDIOC_QBUF,&b))break;}
 ioctl(fd,VIDIOC_STREAMOFF,&type);for(unsigned i=0;i<req.count;i++)munmap(ptr[i],len[i]);close(fd);printf("frames_delivered=%u bytes_discarded=%u no_frames_saved=1\n",frames,bytes);return frames?0:1;
}
