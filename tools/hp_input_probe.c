/* Aggregate input activity and switch state; never records typed text. */
#include <dirent.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int main(int argc,char **argv){
 int seconds=argc>1?atoi(argv[1]):40;struct pollfd p[128];char names[128][256];unsigned long counts[128][EV_MAX+1];unsigned long sw[128];int n=0;
 memset(counts,0,sizeof(counts));memset(sw,0,sizeof(sw));DIR*d=opendir("/dev/input");struct dirent*e;
 if(!d){perror("input devices");return 1;}
 while((e=readdir(d))&&n<128){if(strncmp(e->d_name,"event",5))continue;char path[256];snprintf(path,sizeof(path),"/dev/input/%.200s",e->d_name);int fd=open(path,O_RDONLY|O_NONBLOCK);if(fd<0)continue;p[n]=(struct pollfd){fd,POLLIN,0};strcpy(names[n],path);char name[128]={0};ioctl(fd,EVIOCGNAME(sizeof(name)),name);printf("INPUT %s %s\n",path,name);ioctl(fd,EVIOCGSW(sizeof(sw[n])),&sw[n]);n++;}
 closedir(d);printf("INPUT_EVENT_NODE_COUNT=%d\n",n);fflush(stdout);
 if(!n){puts("INCONCLUSIVE: no readable evdev nodes; check evdev and input-driver modules.");return 1;}
 time_t until=time(NULL)+seconds;
 while(time(NULL)<until){if(poll(p,n,250)<=0)continue;for(int i=0;i<n;i++)if(p[i].revents&POLLIN){struct input_event events[32];ssize_t bytes;while((bytes=read(p[i].fd,events,sizeof(events)))>0){for(unsigned j=0;j<(unsigned)bytes/sizeof(events[0]);j++){struct input_event*x=&events[j];if(x->type<=EV_MAX)counts[i][x->type]++;if(x->type==EV_SW&&x->code<sizeof(long)*8){if(x->value)sw[i]|=1UL<<x->code;else sw[i]&=~(1UL<<x->code);printf("SWITCH %s code=%u value=%d\n",names[i],x->code,x->value);}}}}}
 for(int i=0;i<n;i++){printf("RESULT %s key_events=%lu relative_events=%lu absolute_events=%lu switch_events=%lu switch_state=0x%lx\n",names[i],counts[i][EV_KEY],counts[i][EV_REL],counts[i][EV_ABS],counts[i][EV_SW],sw[i]);close(p[i].fd);}return 0;
}
