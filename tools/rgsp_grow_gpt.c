/* Preserve RGSP's compact GPT: a conventional 128-entry table overlaps Boot0.
 * This helper changes only p8's end and GPT metadata, never formats a volume.
 */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/blkpg.h>
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

static void die(const char *s) { perror(s); exit(1); }
static void require(int ok, const char *s) {
    if (!ok) { fprintf(stderr, "REJECTED: %s\n", s); exit(1); }
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
static void read_at(int fd,void *p,size_t n,uint64_t at) {
    size_t done=0;
    while(done<n) {
        ssize_t r=pread(fd,(char *)p+done,n-done,at+done);
        if(r<=0) die("read");
        done+=(size_t)r;
    }
}
static void write_at(int fd,const void *p,size_t n,uint64_t at) {
    size_t done=0;
    while(done<n) {
        ssize_t r=pwrite(fd,(const char *)p+done,n-done,at+done);
        if(r<=0) die("write");
        done+=(size_t)r;
    }
}
static int valid_header(const unsigned char *h) {
    unsigned char copy[512];
    if(memcmp(h,"EFI PART",8)||u32(h+12)!=92||u32(h+80)!=8||u32(h+84)!=128) return 0;
    memcpy(copy,h,512); put32(copy+16,0);
    return crc(copy,92)==u32(h+16);
}
static void header(unsigned char *h,uint64_t here,uint64_t other,uint64_t entries,
                   uint64_t last,const unsigned char *table) {
    put64(h+24,here); put64(h+32,other); put64(h+40,4); put64(h+48,last);
    put64(h+72,entries); put32(h+88,crc(table,1024));
    put32(h+16,0); put32(h+16,crc(h,92));
}

int main(int argc,char **argv) {
    require(argc==3||argc==4,"usage: rgsp-grow-gpt --check|--apply DEVICE [--image-test]");
    int apply=!strcmp(argv[1],"--apply"), image=argc==4&&!strcmp(argv[3],"--image-test");
    require(apply||!strcmp(argv[1],"--check"),"invalid mode");
    require(argc!=4||image,"invalid test flag");
    int fd=open(argv[2],(apply?O_RDWR:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0) die("open");
    /* udev may briefly hold the freshly discovered device's advisory lock. */
    for(int attempt=0;;attempt++) {
        if(!flock(fd,LOCK_EX|LOCK_NB)) break;
        if(errno!=EWOULDBLOCK||attempt>=50) die("flock");
        usleep(100000);
    }
    struct stat st;
    if(fstat(fd,&st)) die("stat");
    require(image?S_ISREG(st.st_mode):S_ISBLK(st.st_mode),"unexpected file/device type");
    uint64_t bytes=(uint64_t)st.st_size;
    int sector=512;
    if(!image) {
        if(ioctl(fd,BLKGETSIZE64,&bytes)||ioctl(fd,BLKSSZGET,&sector)) die("size ioctl");
    }
    require(sector==512&&bytes%512==0&&bytes>28139585536ULL+512*1024*1024ULL,
            "unsupported sector size or undersized card");
    uint64_t total=bytes/512, last=total-4;
    unsigned char head[2048],table[1024],back[512],oldback[512],verify[2048];
    read_at(fd,head,sizeof(head),0);
    unsigned char *h=head+512;
    int recovered=0;
    if(!valid_header(h) || crc(head+1024,1024)!=u32(h+88)) {
        /* Recover an interrupted primary update only from the physical-end backup. */
        read_at(fd,back,512,(total-1)*512);
        require(valid_header(back)&&u64(back+24)==total-1&&u64(back+32)==1&&
                u64(back+72)==total-3&&u64(back+40)==4&&u64(back+48)==last,
                "no valid recovery GPT");
        read_at(fd,table,1024,(total-3)*512);
        require(crc(table,1024)==u32(back+88),"bad recovery entries");
        memcpy(h,back,512); header(h,1,total-1,2,last,table); recovered=1;
    } else {
        require(u64(h+24)==1&&u64(h+72)==2,"unexpected primary locations");
        memcpy(table,head+1024,1024);
        require(crc(table,1024)==u32(h+88),"primary entry CRC");
    }
    require(head[510]==0x55&&head[511]==0xaa&&head[450]==0xee,"protective MBR missing");
    uint64_t header_backup = u64(h+32), header_last = u64(h+48);
    require(u64(h+40)==4&&header_backup>4&&header_backup<total&&
            header_last==header_backup-3,"GPT device bounds");
    static const uint64_t starts[]={37748736,104857600,138412032,155189248,
        222298112,8812232704,10959716352,28139585536};
    static const uint64_t lengths[]={67108864,33554432,16777216,67108864,
        8589934592ULL,2147483648ULL,17179869184ULL};
    static const char *names[]={"special","boot-resource","env","boot","system","vendor","data","ROMS"};
    static const unsigned char basic[]={0xa2,0xa0,0xd0,0xeb,0xe5,0xb9,0x33,0x44,0x87,0xc0,0x68,0xb6,0xb7,0x26,0x99,0xc7};
    static const unsigned char linux_type[]={0xaf,0x3d,0xc6,0x0f,0x83,0x84,0x72,0x47,0x8e,0x79,0x3d,0x69,0xd8,0x47,0x7d,0xe4};
    for(int i=0;i<8;i++) {
        unsigned char *e=table+i*128;
        require(u64(e+32)*512==starts[i],"unexpected partition start");
        require(!memcmp(e,(i>=4&&i<=6)?linux_type:basic,16),"unexpected partition type");
        for(size_t j=0;j<=strlen(names[i]);j++)
            require(e[56+2*j]==(unsigned char)names[i][j]&&e[57+2*j]==0,"unexpected partition name");
        if(i<7) require((u64(e+40)+1)*512==starts[i]+lengths[i],"protected partition size");
    }
    uint64_t oldend=u64(table+7*128+40), start=starts[7]/512;
    /* U-Boot may normalize GPT's usable range to the physical card while
     * leaving p8 at the compact image end. Both states are valid inputs. */
    require(oldend<=last&&oldend>start+65536&&
            (header_last==oldend||header_last==last),"invalid ROMS end");
    if(!recovered) {
        read_at(fd,oldback,512,u64(h+32)*512);
        require(valid_header(oldback)&&u64(oldback+24)==u64(h+32)&&u64(oldback+32)==1&&
            u64(oldback+72)==u64(h+32)-2&&u32(oldback+88)==u32(h+88)&&
            !memcmp(oldback+56,h+56,16),"backup GPT does not match primary");
        unsigned char oldtable[1024];
        read_at(fd,oldtable,1024,u64(oldback+72)*512);
        require(!memcmp(table,oldtable,1024),"backup entries differ");
    }
    printf("OLD_END=%" PRIu64 "\nNEW_END=%" PRIu64 "\nROMS_BYTES=%" PRIu64 "\n",
           oldend,last,(last-start+1)*512);
    if(apply&&(oldend!=last||recovered)) {
        put64(table+7*128+40,last);
        memcpy(back,h,512);
        header(back,total-1,1,total-3,last,table);
        header(h,1,total-1,2,last,table);
        memcpy(head+1024,table,1024);
        put32(head+458,total-1>UINT32_MAX?UINT32_MAX:(uint32_t)(total-1));
        write_at(fd,table,1024,(total-3)*512);
        write_at(fd,back,512,(total-1)*512);
        if(fsync(fd)) die("backup fsync");
        write_at(fd,head,2048,0);
        if(fsync(fd)) die("primary fsync");
        read_at(fd,verify,2048,0);
        require(!memcmp(head,verify,2048),"primary readback mismatch");
        read_at(fd,verify,1024,(total-3)*512);
        read_at(fd,verify+1024,512,(total-1)*512);
        require(!memcmp(table,verify,1024)&&!memcmp(back,verify+1024,512),"backup readback mismatch");
    }
    if(apply&&!image) {
        /* Do not request a resize on every boot; unsupported ioctls must not
         * cause a reboot loop after the on-disk GPT is already correct. */
        char sys_path[160];
        snprintf(sys_path,sizeof(sys_path),"/sys/dev/block/%u:%u/%sp8/size",
            major(st.st_rdev),minor(st.st_rdev),strrchr(argv[2],'/')?strrchr(argv[2],'/')+1:argv[2]);
        FILE *size_file=fopen(sys_path,"r");
        uint64_t kernel_sectors=0;
        if(size_file) {
            int parsed=fscanf(size_file,"%" SCNu64,&kernel_sectors);
            fclose(size_file);
            if(parsed==1&&kernel_sectors==last-start+1) {
                close(fd); puts("GPT_APPLY_VERIFIED"); return 0;
            }
        }
        /* Update p8 only, even if other partitions are already mounted. */
        struct blkpg_partition part={0};
        part.pno=8; part.start=(long long)(start*512); part.length=(long long)((last-start+1)*512);
        struct blkpg_ioctl_arg arg={.op=BLKPG_RESIZE_PARTITION,.datalen=sizeof(part),.data=&part};
        if(ioctl(fd,BLKPG,&arg)) { perror("partition refresh requires reboot"); close(fd); return 3; }
    }
    close(fd);
    puts(apply?"GPT_APPLY_VERIFIED":"GPT_CHECK_OK");
    return 0;
}
