/* Syscall-only mount helper. Refuses the caller's original mount namespace. */
static long call(long n,long a,long b,long c,long d,long e) {
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
 register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x8 __asm__("x8")=n;
 __asm__ volatile("svc #0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x8):"memory");return x0;
}
#ifndef ROOTFS_PREFIX
#define ROOTFS_PREFIX "/data/local/tmp/h700-arm64-isolated-20261030/rootfs/"
#endif
static int same(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int guarded_mount(long argc,char**argv) {
 if(argc!=2&&argc!=3&&argc!=4)return 2;
 char current[96];long n=call(78,-100,(long)"/proc/self/ns/mnt",(long)current,95,0);
 if(n<=0||n>=95)return 3;current[n]=0;
 if(same(current,argv[1]))return 4;
 long r;
 if(argc==2)r=call(40,0,(long)"/",0,0x44000,0); /* MS_PRIVATE|MS_REC */
 else {
  const char *target=argv[argc-1];
  const char *p=target,*q=ROOTFS_PREFIX;
  while(*q&&*q==*p){q++;p++;}if(*q)return 5;
  for(const char*t=p;*t;t++)if(t[0]=='.'&&t[1]=='.')return 6;
  if(argc==4) {
   static const char * const allowed[]={"/proc","/sys","/dev/__properties__","/dev/null","/dev/zero","/dev/urandom","/dev/random","/dev/ashmem","/dev/binder","/dev/hwbinder","/dev/vndbinder","/dev/mali0","/dev/ion"};
   int ok=0;for(unsigned i=0;i<sizeof(allowed)/sizeof(allowed[0]);i++)if(same(argv[2],allowed[i]))ok=1;
   if(!ok)return 7;
   r=call(40,(long)argv[2],(long)target,0,0x1000,0); /* MS_BIND */
  } else r=call(40,0,(long)target,0,0x1021,0);
 }
 return r<0?(int)-r:0;
}
__asm__(".global _start\n_start:\nldr x0,[sp]\nadd x1,sp,#8\nbl guarded_mount\nmov x8,#93\nsvc #0\n");
