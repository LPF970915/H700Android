/* SPDX-License-Identifier: Apache-2.0
 * ROC unified userdata only. Metadata-first recovery; never formats a volume.
 */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/fs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include "identity.h"

static void need(int ok, const char *s) {
    if (!ok) { fprintf(stderr, "ROC_GROW_REJECTED: %s\n", s); exit(1); }
}
static uint32_t u32(const void *p) { uint32_t v; memcpy(&v,p,4); return v; }
static uint64_t u64(const void *p) { uint64_t v; memcpy(&v,p,8); return v; }
static void put32(void *p,uint32_t v) { memcpy(p,&v,4); }
static void put64(void *p,uint64_t v) { memcpy(p,&v,8); }
static uint32_t crc(const unsigned char *p,size_t n) {
    uint32_t c=~0U;
    while(n--) { c^=*p++; for(int i=0;i<8;i++) c=(c>>1)^((0U-(c&1))&0xedb88320U); }
    return ~c;
}
static void io_at(int fd,void *buf,size_t n,uint64_t at,int writing) {
    size_t done=0;
    while(done<n) {
        ssize_t r=writing?pwrite(fd,(char*)buf+done,n-done,at+done):pread(fd,(char*)buf+done,n-done,at+done);
        need(r>0,writing?"metadata write":"metadata read"); done+=(size_t)r;
    }
}
static int valid(const unsigned char *h,const unsigned char *table) {
    unsigned char copy[512]; memcpy(copy,h,512); put32(copy+16,0);
    return !memcmp(h,"EFI PART",8) && u32(h+12)==92 && u32(h+80)==8 && u32(h+84)==128 &&
        crc(copy,92)==u32(h+16) && crc(table,1024)==u32(h+88);
}
static void header(unsigned char *h,const unsigned char *table,uint64_t here,uint64_t other,uint64_t entries,uint64_t last) {
    put64(h+24,here); put64(h+32,other); put64(h+40,4); put64(h+48,last); put64(h+72,entries);
    put32(h+88,crc(table,1024)); put32(h+16,0); put32(h+16,crc(h,92));
}
int main(int argc,char **argv) {
    need(argc==3||argc==4,"usage: --check|--apply DISK or --check-volume PARTITION [--image-test]");
    int apply=!strcmp(argv[1],"--apply"), fixture=argc==4&&!strcmp(argv[3],"--image-test");
    int volume=!strcmp(argv[1],"--check-volume");
    need(apply||volume||!strcmp(argv[1],"--check"),"mode"); need(argc==3||fixture,"test flag");
    int fd=open(argv[2],(apply?O_RDWR:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW); need(fd>=0,"open");
    need(!flock(fd,LOCK_EX|LOCK_NB),"busy"); struct stat st; need(!fstat(fd,&st),"stat");
    need(fixture?S_ISREG(st.st_mode):S_ISBLK(st.st_mode),"file type");
    uint64_t bytes=st.st_size; int sector=512;
    if (!fixture) need(!ioctl(fd,BLKGETSIZE64,&bytes)&&!ioctl(fd,BLKSSZGET,&sector),"capacity");
    if(volume) {
        unsigned char sb[1024]; io_at(fd,sb,1024,1024,0);
        const unsigned char fsid[16]=ROC_DATA_FS_UUID_BYTES;
        need(sb[56]==0x53&&sb[57]==0xef&&!memcmp(sb+104,fsid,16),"userdata filesystem identity");
        need(u32(sb+24)<=6,"ext4 block size"); uint64_t block=1024ULL<<u32(sb+24),blocks=u32(sb+4);
        if(u32(sb+96)&0x80) blocks|=(uint64_t)u32(sb+336)<<32;
        need(blocks<=bytes/block,"filesystem larger than partition");
        printf("ROC_EXT4_BLOCKS=%" PRIu64 " TARGET=%" PRIu64 "\n",blocks,bytes/block);
        close(fd); return blocks==bytes/block?0:4;
    }
    need(sector==512&&bytes%512==0&&bytes>=32434554368ULL,"capacity/sector");
    uint64_t total=bytes/512,last=total-4;
    unsigned char head[2048],table[1024],back[512],verify[2048],endtable[1024];
    io_at(fd,head,sizeof(head),0,0);
    need(head[510]==0x55&&head[511]==0xaa&&head[450]==0xee,"protective MBR");
    unsigned char *h=head+512; int recovered=0;
    if (valid(h,head+1024)&&u64(h+24)==1&&u64(h+72)==2) memcpy(table,head+1024,1024);
    else {
        io_at(fd,back,512,(total-1)*512,0); io_at(fd,table,1024,(total-3)*512,0);
        need(valid(back,table)&&u64(back+24)==total-1&&u64(back+32)==1&&u64(back+72)==total-3,"no valid recovery GPT");
        memcpy(h,back,512); recovered=1;
    }
    const unsigned char disk_id[16]=ROC_DISK_GUID_BYTES,data_id[16]=ROC_DATA_GUID_BYTES,linux_type[16]=ROC_LINUX_TYPE_BYTES;
    need(!memcmp(h+56,disk_id,16),"wrong disk identity");
    const uint64_t starts[]={73728,204800,270336,303104,434176,17211392};
    const uint64_t lengths[]={131072,65536,32768,131072,16777216,4194304};
    const char *names[]={"special","boot-resource","env","boot","system","vendor","userdata"};
    for(int i=0;i<7;i++) {
        unsigned char name[72]={0}; for(size_t k=0;k<strlen(names[i]);k++) name[k*2]=names[i][k];
        need(!memcmp(table+i*128+56,name,72),"partition name");
        if(i<6) need(u64(table+i*128+32)==starts[i]&&u64(table+i*128+40)==starts[i]+lengths[i]-1,"protected extent");
    }
    unsigned char zero[128]={0}; need(!memcmp(table+896,zero,128),"p8 must be unused");
    need(!memcmp(table+768,linux_type,16)&&!memcmp(table+784,data_id,16)&&u64(table+800)==21405696,"userdata identity/start");
    need(u64(table+808)<=last&&u64(table+808)>=32434554368ULL/512-4,"refuse shrinking");
    if(!fixture) {
        FILE *f=fopen("/proc/self/mountinfo","r"); need(f!=NULL,"mount guard");
        char *line=NULL; size_t n=0; unsigned int ma,mi; unsigned long a,b;
        char sys[256],base[4096]; snprintf(sys,sizeof(sys),"/sys/dev/block/%u:%u",major(st.st_rdev),minor(st.st_rdev));
        need(realpath(sys,base)!=NULL&&strstr(base,"/sdc0/")!=NULL,"TF1 controller");
        while(getline(&line,&n,f)>0) if(sscanf(line,"%lu %lu %u:%u",&a,&b,&ma,&mi)==4) {
            char path[4096]; snprintf(sys,sizeof(sys),"/sys/dev/block/%u:%u",ma,mi);
            if(realpath(sys,path)) need(strncmp(path,base,strlen(base))!=0,"boot-card partition mounted");
        }
        free(line); fclose(f);
    }
    io_at(fd,back,512,(total-1)*512,0); io_at(fd,endtable,1024,(total-3)*512,0);
    int backup_ok=valid(back,endtable)&&u64(back+24)==total-1&&u64(back+32)==1&&
        u64(back+72)==total-3&&!memcmp(endtable,table,1024);
    int changed=recovered||!backup_ok||u64(table+808)!=last||u64(h+32)!=total-1;
    printf("ROC_USERDATA_TARGET_SECTORS=%" PRIu64 "\n",last-21405696+1);
    if(!apply) { close(fd); return changed?4:0; }
    if(changed) {
        put64(table+808,last); memcpy(back,h,512); header(back,table,total-1,1,total-3,last);
        io_at(fd,table,1024,(total-3)*512,1); io_at(fd,back,512,(total-1)*512,1); need(!fsync(fd),"backup sync");
        unsigned char checkback[512]; io_at(fd,checkback,512,(total-1)*512,0); io_at(fd,endtable,1024,(total-3)*512,0);
        need(!memcmp(checkback,back,512)&&!memcmp(endtable,table,1024),"backup readback");
        header(h,table,1,total-1,2,last); memcpy(head+1024,table,1024); put32(head+458,total-1>0xffffffff?0xffffffff:(uint32_t)(total-1));
        io_at(fd,head,2048,0,1); need(!fsync(fd),"primary sync"); io_at(fd,verify,2048,0,0); need(!memcmp(head,verify,2048),"readback");
    }
    if(!fixture&&ioctl(fd,BLKRRPART)) { close(fd); return 4; } // Reboot before filesystem growth.
    close(fd); return 0;
}
