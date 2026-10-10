/* Optional RTC-woken suspend test; restore the previous alarm on return. */
#include <fcntl.h>
#include <linux/rtc.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
int main(void){
 int rtc=open("/dev/rtc0",O_RDWR);if(rtc<0){perror("rtc0");return 1;}
 struct rtc_wkalrm old={0},alarm={0};struct rtc_time now={0};
 if(ioctl(rtc,RTC_WKALM_RD,&old)||ioctl(rtc,RTC_RD_TIME,&now)){perror("read RTC/alarm; refusing suspend");close(rtc);return 1;}
 struct tm t={.tm_sec=now.tm_sec,.tm_min=now.tm_min,.tm_hour=now.tm_hour,.tm_mday=now.tm_mday,.tm_mon=now.tm_mon,.tm_year=now.tm_year};
 time_t seconds=timegm(&t)+20;struct tm*a=gmtime(&seconds);
 alarm.enabled=1;alarm.time=(struct rtc_time){.tm_sec=a->tm_sec,.tm_min=a->tm_min,.tm_hour=a->tm_hour,.tm_mday=a->tm_mday,.tm_mon=a->tm_mon,.tm_year=a->tm_year,.tm_wday=a->tm_wday,.tm_yday=a->tm_yday,.tm_isdst=0};
 if(ioctl(rtc,RTC_WKALM_SET,&alarm)){perror("set wake alarm; refusing suspend");close(rtc);return 1;}
 puts("Suspending with RTC wake in 20 seconds. If no return after 60 seconds, use the power button.");fflush(stdout);sync();
 int power=open("/sys/power/state",O_WRONLY);int result=1;
 if(power>=0){result=write(power,"mem",3)==3?0:1;close(power);}else perror("power/state");
 if(ioctl(rtc,RTC_WKALM_SET,&old))perror("restore original wake alarm");close(rtc);
 printf("SUSPEND_RETURNED status=%d (return alone does not establish duration or all peripheral recovery)\n",result);return result;
}
