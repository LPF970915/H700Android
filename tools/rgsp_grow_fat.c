/* Only libparted's filesystem API is used. No disk-label/GPT commits. */
#include <parted/parted.h>
#include <parted/filesys.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static uint32_t le32(const unsigned char *p) {
    return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static PedExceptionOption stop_on_error(PedException *e) {
    fprintf(stderr, "FAT: %s\n", e->message);
    return PED_EXCEPTION_CANCEL;
}
int main(int argc, char **argv) {
    int check=argc==3&&!strcmp(argv[2],"--check");
    if (argc != 2 && !check) { fprintf(stderr,"usage: rgsp-grow-fat UNMOUNTED_FAT32_VOLUME [--check]\n"); return 2; }
    ped_exception_set_handler(stop_on_error);
    PedDevice *dev=ped_device_get(argv[1]);
    if (!dev || dev->sector_size!=512 || !ped_device_open(dev)) return 1;
    PedGeometry *whole=ped_geometry_new(dev,0,dev->length);
    if (!whole) return 1;
    /* Avoid loading a terabyte volume's whole FAT merely to check its size. */
    unsigned char boot[512];
    if (!ped_device_read(dev,boot,0,1) || boot[510]!=0x55 || boot[511]!=0xaa ||
        boot[11]!=0 || boot[12]!=2 || !boot[13] || (boot[13]&(boot[13]-1)) ||
        boot[17] || boot[18] || boot[22] || boot[23] || !le32(boot+36)) {
        fprintf(stderr,"Invalid FAT32 boot sector\n"); return 1;
    }
    uint32_t sectors=le32(boot+32);
    if (!sectors || (PedSector)sectors>dev->length) {
        fprintf(stderr,"FAT32 exceeds its device\n"); return 1;
    }
    if (dev->length-sectors<2048) {
        puts("FAT_ALREADY_FULL");
        ped_geometry_destroy(whole); ped_device_close(dev); return 0;
    }
    if (check) {
        puts("FAT_NEEDS_GROW");
        ped_geometry_destroy(whole); ped_device_close(dev); return 4;
    }
    const PedFileSystemType *type=ped_file_system_probe(whole);
    if (!type || strcmp(type->name,"fat32")) {
        fprintf(stderr,"Refusing non-FAT32 volume\n"); return 1;
    }
    PedFileSystem *fs=ped_file_system_open(whole);
    if (!fs) return 1;
    PedConstraint *constraint=ped_file_system_get_resize_constraint(fs);
    if (!constraint) return 1;
    PedGeometry *goal=ped_constraint_solve_nearest(constraint,whole);
    if (!goal || goal->start!=0 || dev->length-goal->length>=2048) {
        fprintf(stderr,"FAT32 constraint: device=%lld nearest_start=%lld nearest_size=%lld\n",
            (long long)dev->length,goal?(long long)goal->start:-1LL,
            goal?(long long)goal->length:-1LL);
        return 1;
    }
    printf("FAT_GROW old_sectors=%lld new_sectors=%lld\n",
           (long long)fs->geom->length,(long long)goal->length);
    fflush(stdout);
    if (!ped_file_system_resize(fs,goal,NULL)) return 1;
    ped_geometry_destroy(goal);
    ped_constraint_destroy(constraint);
    if (!ped_file_system_close(fs) || !ped_device_sync(dev)) return 1;
    ped_geometry_destroy(whole); ped_device_close(dev);
    puts("FAT_GROW_COMPLETE");
    return 0;
}
