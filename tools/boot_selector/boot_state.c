/* ROC selector boot-state helper. Runs only in the reviewed pre-Android init.
 * Edits a CRC checked, explicitly marked environment partition, preserving
 * all unrelated keys. The host test mode accepts an ordinary 16MiB fixture.
 */
#define _GNU_SOURCE
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/file.h>
#include <linux/fs.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ENV_BYTES (128U*1024U)
#define PART_BYTES (16U*1024U*1024U)
#define MAX_ROWS 256
static unsigned char before[ENV_BYTES], after[ENV_BYTES], checkbuf[ENV_BYTES];
struct row { char *key; char *value; };
static struct row rows[MAX_ROWS];
static int row_count;
static int leading_empty;
static const char *models[] = {"rg34xx","rg34xxsp","rgsp","rgcubexx","rg35xxplus",
    "rg35xx_2025","rg28xx","rg35xxh","rg40xxh","rg40xxv","rg35xxsp","rg35xxpro"};

static void die(const char *why) { fprintf(stderr,"[roc-selector-state] %s: %s\n",why,strerror(errno)); exit(2); }
static void require(int ok,const char *why) { if(!ok) { errno=EINVAL;die(why); } }
static uint32_t get32(const unsigned char *p) { return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24; }
static void put32(unsigned char *p,uint32_t n) { for(int i=0;i<4;i++)p[i]=(unsigned char)(n>>(8*i)); }
static uint32_t crc32(const unsigned char *p,size_t n) {
    uint32_t c=~0U;while(n--) { c^=*p++;for(int k=0;k<8;k++)c=(c>>1)^(0xedb88320U&-(int32_t)(c&1)); }return ~c;
}
static int valid_model(const char *s) { for(unsigned i=0;i<sizeof(models)/sizeof(*models);i++)if(!strcmp(s,models[i]))return 1;return 0; }
static const char *get(const char *key) { for(int i=0;i<row_count;i++)if(!strcmp(rows[i].key,key))return rows[i].value;return ""; }
static void parse(void) {
    require(get32(before)==crc32(before+4,ENV_BYTES-4),"environment CRC mismatch");
    size_t p=4;row_count=0;
    leading_empty=before[p]==0 && before[p+1]!=0;
    if(leading_empty)p++; /* retained vendor leading empty row */
    while(p<ENV_BYTES && before[p]) {
        size_t start=p;while(p<ENV_BYTES && before[p])p++;
        require(p<ENV_BYTES && row_count<MAX_ROWS,"unterminated/oversized environment");
        char *text=(char*)before+start,*eq=strchr(text,'=');
        require(eq && eq!=text,"malformed environment row");*eq=0;
        for(char *s=text;*s;s++)require((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||(*s>='0'&&*s<='9')||*s=='_'||*s=='.',"bad environment key");
        for(int i=0;i<row_count;i++)require(strcmp(rows[i].key,text)!=0,"duplicate environment key");
        rows[row_count++]=(struct row){text,eq+1};p++;
    }
    require(p<ENV_BYTES-1 && before[p]==0,"missing environment terminator");
    for(size_t i=p;i<ENV_BYTES;i++)require(before[i]==0,"nonzero environment padding");
    require(!strcmp(get("roc_selector_schema"),"2"),"not an integrated ROC selector environment");
    require(strstr(get("boot_normal"),"run roc_selector_apply")!=NULL&&*get("roc_selector_apply"),"boot hook missing");
    const char *saved=get("roc_saved_model"),*next=get("roc_next_model"),*start=get("roc_next_start");
    require(!*saved||valid_model(saved),"bad saved model");
    require(!*next||valid_model(next),"bad next model");
    require(!*start||!strcmp(start,"1"),"bad next_start");
    require((!!*next)==(!!*start),"incomplete one-shot selection");
}
static int owned(const char *k) {return !strcmp(k,"roc_saved_model")||!strcmp(k,"roc_next_model")||!strcmp(k,"roc_next_start");}
static void append(size_t *pos,const char *key,const char *value) {
    size_t k=strlen(key),v=strlen(value);require(*pos+k+v+3<ENV_BYTES,"environment full");
    memcpy(after+*pos,key,k);*pos+=k;after[(*pos)++]='=';memcpy(after+*pos,value,v);*pos+=v;after[(*pos)++]=0;
}
static void exact_read(int fd,unsigned char *p,size_t n) {
    size_t used=0;while(used<n){ssize_t r=pread(fd,p+used,n-used,(off_t)used);if(r<0&&errno==EINTR)continue;if(r<=0)die("short environment read");used+=(size_t)r;}
}
static int exact_write(int fd,const unsigned char *p,size_t n) {
    size_t used=0;while(used<n){ssize_t r=pwrite(fd,p+used,n-used,(off_t)used);if(r<0&&errno==EINTR)continue;if(r<=0)return -1;used+=(size_t)r;}return 0;
}
static void skip_space(const char **p) {while(**p==' '||**p=='\t'||**p=='\r'||**p=='\n')(*p)++;}
static void json_string(const char **p,char *out,size_t capacity) {
    skip_space(p);require(*(*p)++=='"',"result JSON string required");size_t used=0;
    while(**p&&**p!='"'){unsigned char c=(unsigned char)*(*p)++;require(c>=32&&c<127&&c!='\\'&&used+1<capacity,"unsupported result JSON string");out[used++]=(char)c;}
    require(*(*p)++=='"',"unterminated result JSON string");out[used]=0;
}
static int parse_result(const char *path) {
    int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);if(fd<0)die("open result");struct stat st;
    if(fstat(fd,&st)<0)die("stat result");
    require(S_ISREG(st.st_mode)&&st.st_nlink==1&&st.st_size>0&&st.st_size<=512,"result must be small single-link regular file");
    char raw[513];size_t used=0;while(used<(size_t)st.st_size){ssize_t n=read(fd,raw+used,(size_t)st.st_size-used);if(n<0&&errno==EINTR)continue;if(n<=0)die("short result read");used+=(size_t)n;}
    char extra;require(read(fd,&extra,1)==0,"result grew during read");struct stat afterstat;if(fstat(fd,&afterstat)<0)die("restat result");require(afterstat.st_size==st.st_size&&afterstat.st_mtim.tv_sec==st.st_mtim.tv_sec&&afterstat.st_mtim.tv_nsec==st.st_mtim.tv_nsec,"result changed during read");close(fd);
    require(!memchr(raw,0,used),"NUL in result JSON");raw[used]=0;const char *p=raw;skip_space(&p);require(*p++=='{',"result JSON object required");unsigned fields=0;char model[64]="";int save=0;
    for(unsigned count=0;count<3;count++){
        char key[32];json_string(&p,key,sizeof(key));skip_space(&p);require(*p++==':',"result JSON colon required");skip_space(&p);
        if(!strcmp(key,"schema")){require(!(fields&1),"duplicate result schema");fields|=1;require(*p++=='2',"result schema must be integer 2");}
        else if(!strcmp(key,"model_id")){require(!(fields&2),"duplicate result model");fields|=2;json_string(&p,model,sizeof(model));require(valid_model(model),"unknown result model");}
        else if(!strcmp(key,"save_default")){require(!(fields&4),"duplicate result save");fields|=4;if(!strncmp(p,"true",4)){save=1;p+=4;}else if(!strncmp(p,"false",5)){save=0;p+=5;}else require(0,"result save must be boolean");}
        else require(0,"unknown result JSON field");
        skip_space(&p);require(*p++==(count==2?'}':','),"result JSON field count or separator");
    }
    skip_space(&p);require(!*p&&fields==7,"trailing result JSON or missing fields");printf("model=%s\nsave=%d\n",model,save);return 0;
}
int main(int argc,char **argv) {
    if(argc==3&&!strcmp(argv[1],"--result"))return parse_result(argv[2]);
    require(argc>=4,"usage: boot-state [--fixture|--partition] path status|clear-next|save|once [model]");
    int fixture=!strcmp(argv[1],"--fixture");require(fixture||!strcmp(argv[1],"--partition"),"explicit target kind required");
    int writing=strcmp(argv[3],"status")!=0;
    if(writing)require(!strcmp(argv[3],"clear-next")||!strcmp(argv[3],"save")||!strcmp(argv[3],"once"),"unknown action");
    if(!strcmp(argv[3],"save")||!strcmp(argv[3],"once"))require(argc==5&&valid_model(argv[4]),"unknown model");
    else require(argc==4,"extra arguments");
    int fd=open(argv[2],(writing?O_RDWR:O_RDONLY)|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);if(fd<0)die("open target");
    struct stat st;if(fstat(fd,&st)<0)die("stat target");uint64_t size=0;
    if(fixture){require(S_ISREG(st.st_mode)&&st.st_nlink==1,"fixture must be single-link ordinary file");size=(uint64_t)st.st_size;}
    else{require(S_ISBLK(st.st_mode),"partition must be block device");if(ioctl(fd,BLKGETSIZE64,&size)<0)die("partition size");}
    require(size==PART_BYTES,"wrong environment partition size");if(flock(fd,LOCK_EX|LOCK_NB)<0)die("environment busy");
    exact_read(fd,before,ENV_BYTES);memcpy(checkbuf,before,ENV_BYTES);parse();
    if(!writing){
        const char *saved=get("roc_saved_model"),*next=get("roc_next_model");
        printf("saved=%s\nnext=%s\nnext_start=%s\n",saved,next,get("roc_next_start"));close(fd);return 0;
    }
    memset(after,0,ENV_BYTES);size_t p=4+(unsigned)leading_empty;
    for(int i=0;i<row_count;i++)if(!owned(rows[i].key))append(&p,rows[i].key,rows[i].value);
    const char *saved=get("roc_saved_model");require(!*saved||valid_model(saved),"invalid prior saved model");
    if(!strcmp(argv[3],"save"))saved=argv[4];
    if(*saved)append(&p,"roc_saved_model",saved);
    if(!strcmp(argv[3],"once")){append(&p,"roc_next_model",argv[4]);append(&p,"roc_next_start","1");}
    put32(after,crc32(after+4,ENV_BYTES-4));
    exact_read(fd,before,ENV_BYTES);require(!memcmp(before,checkbuf,ENV_BYTES),"environment changed concurrently");
    if(!memcmp(before,after,ENV_BYTES)){close(fd);return 0;}
    if(exact_write(fd,after,ENV_BYTES)<0||fsync(fd)<0){int e=errno;exact_write(fd,checkbuf,ENV_BYTES);fsync(fd);errno=e;die("write failed; original restoration attempted");}
    exact_read(fd,before,ENV_BYTES);
    if(memcmp(before,after,ENV_BYTES)){exact_write(fd,checkbuf,ENV_BYTES);fsync(fd);errno=EIO;die("readback failed; original restoration attempted");}
    close(fd);puts("[roc-selector-state] verified environment update");return 0;
}
