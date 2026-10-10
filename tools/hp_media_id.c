/* Read-only identity gate for GBRUNCH diagnostic log storage. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static uint32_t le32(const unsigned char*p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static uint64_t le64(const unsigned char*p){return le32(p)|((uint64_t)le32(p+4)<<32);}
static uint32_t crc32(const unsigned char*p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(int j=0;j<8;j++)c=(c>>1)^((c&1)?0xedb88320:0);}return ~c;}
static int read_at(int fd,void*p,size_t n,uint64_t offset){return pread(fd,p,n,offset)==(ssize_t)n;}
int main(int argc,char**argv){
 if(argc!=3){fprintf(stderr,"usage: hp-media-id PARTITION PARENT_DISK\n");return 2;}
 int disk=open(argv[2],O_RDONLY|O_CLOEXEC),part=open(argv[1],O_RDONLY|O_CLOEXEC);
 if(disk<0||part<0)return 1;
 unsigned char h[512],fat[512];
 if(!read_at(disk,h,512,512)||memcmp(h,"EFI PART",8)||le32(h+12)!=92)return 1;
 uint32_t saved=le32(h+16);memset(h+16,0,4);if(crc32(h,92)!=saved)return 1;
 /* UUID bytes_le for the owned diagnostic disk/partition. */
 const unsigned char dg[16]={0x12,0x48,0x50,0x47,0x42,0x52,0x47,0x4b,0x9e,0x53,0xf1,0x43,0xc8,0x2f,0x51,0x7a};
 const unsigned char pg[16]={0x13,0x48,0x50,0x47,0x42,0x52,0x47,0x4b,0x9e,0x53,0xf1,0x43,0xc8,0x2f,0x51,0x7a};
 if(memcmp(h+56,dg,16)||le32(h+80)!=128||le32(h+84)!=128)return 1;
 unsigned char table[16384];if(!read_at(disk,table,sizeof table,le64(h+72)*512)||crc32(table,sizeof table)!=le32(h+88))return 1;
 if(memcmp(table+16,pg,16)||le64(table+32)!=2048)return 1;
 if(!read_at(part,fat,512,0)||fat[510]!=0x55||fat[511]!=0xaa||memcmp(fat+82,"FAT32   ",8)||le32(fat+67)!=0x47424832)return 1;
 unsigned char parent_fat[512];if(!read_at(disk,parent_fat,512,le64(table+32)*512)||memcmp(fat,parent_fat,512))return 1;
 printf("GBRUNCH_DIAGNOSTIC_MEDIA_CONFIRMED %s %s\n",argv[1],argv[2]);return 0;
}
