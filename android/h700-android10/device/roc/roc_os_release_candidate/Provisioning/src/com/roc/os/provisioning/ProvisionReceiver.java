// SPDX-License-Identifier: Apache-2.0
package com.roc.os.provisioning;
import android.app.role.RoleManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Process;
import android.os.SystemProperties;
import android.os.UserHandle;
import android.provider.Settings;
import android.provider.MediaStore;
import android.content.ContentValues;
import android.content.ComponentName;
import android.database.Cursor;
import android.net.Uri;
import java.io.File;
import java.io.OutputStream;
import android.util.Log;
import android.view.inputmethod.InputMethodManager;
import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
public final class ProvisionReceiver extends BroadcastReceiver {
 private static final String TAG="ROCProvisioning";
 private static final String HOME="com.overdevs.at4k";
 private static final String IME="com.android.inputmethod.leanback/.service.LeanbackImeService";
 private static final String NAV="com.roc.rgsp.navtrial/.NavigationService";
 @Override public void onReceive(Context c,Intent intent) {
  if(!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction()))return;
  if(!ProvisionPolicy.supported(Build.DEVICE,SystemProperties.get("persist.vendor.rgsp.input_profile"),SystemProperties.get("ro.roc.source64.round"),UserHandle.myUserId()))return;
  PendingResult pending=goAsync();
  new Thread(()->{Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND);
   try { configure(c.createDeviceProtectedStorageContext()); }
   catch(Exception e){Log.e(TAG,"Provisioning incomplete; retry next boot",e);}
   finally {pending.finish();}
  },"roc-provision").start();
 }
 private static void secure(Context c,String key,String value) {
  if(!Settings.Secure.putString(c.getContentResolver(),key,value)||!value.equals(Settings.Secure.getString(c.getContentResolver(),key)))throw new IllegalStateException("Secure setting not retained: "+key);
 }
 private static void global(Context c,String key,String value) {
  if(!Settings.Global.putString(c.getContentResolver(),key,value)||!value.equals(Settings.Global.getString(c.getContentResolver(),key)))throw new IllegalStateException("Global setting not retained: "+key);
 }
 private static void checkKeyboard(Context c)throws Exception {
  ApplicationInfo app=c.getPackageManager().getApplicationInfo("com.android.inputmethod.leanback",0);
  MessageDigest d=MessageDigest.getInstance("SHA-256");
  try(FileInputStream f=new FileInputStream(app.sourceDir)){byte[] buf=new byte[65536];for(int n;(n=f.read(buf))>0;)d.update(buf,0,n);}
  StringBuilder actual=new StringBuilder();for(byte b:d.digest())actual.append(String.format("%02x",b&255));
  String expected=new String(Files.readAllBytes(Paths.get("/system/etc/rgsp/leanback.sha256")),StandardCharsets.US_ASCII).trim();
  if(!actual.toString().equals(expected))throw new SecurityException("Keyboard image hash mismatch");
  InputMethodManager manager=c.getSystemService(InputMethodManager.class);
  if(manager==null||manager.getInputMethodList().stream().noneMatch(i->IME.equals(i.getId())))throw new IllegalStateException("Keyboard service unavailable");
 }
 private static void home(Context c)throws Exception {
  RoleManager roles=c.getSystemService(RoleManager.class);if(roles==null)throw new IllegalStateException("RoleManager unavailable");
  c.getPackageManager().getApplicationInfo(HOME,0);
  if(!roles.getRoleHoldersAsUser(RoleManager.ROLE_HOME,UserHandle.SYSTEM).contains(HOME)) {
   CountDownLatch done=new CountDownLatch(1);AtomicBoolean success=new AtomicBoolean();
   roles.addRoleHolderAsUser(RoleManager.ROLE_HOME,HOME,0,UserHandle.SYSTEM,c.getMainExecutor(),ok->{success.set(ok);done.countDown();});
   if(!done.await(12,TimeUnit.SECONDS)||!success.get())throw new IllegalStateException("HOME role assignment failed");
  }
  Intent i=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME);
  if(c.getPackageManager().resolveActivity(i,PackageManager.MATCH_DEFAULT_ONLY)==null||!HOME.equals(c.getPackageManager().resolveActivity(i,PackageManager.MATCH_DEFAULT_ONLY).activityInfo.packageName))throw new IllegalStateException("HOME resolution mismatch");
 }
 private static void networkDefaults(Context c) {
  String[][] defaults={{"captive_portal_https_url","https://connectivitycheck.platform.hicloud.com/generate_204"},
   {"captive_portal_http_url","http://connect.rom.miui.com/generate_204"},
   {"captive_portal_fallback_url","http://connectivitycheck.platform.hicloud.com/generate_204"},
   {"captive_portal_other_fallback_urls","http://connect.rom.miui.com/generate_204"}};
  for(String[] item:defaults) {
   String old=Settings.Global.getString(c.getContentResolver(),item[0]);
   if(old==null||old.isEmpty())global(c,item[0],item[1]);
  }
 }
 private static void launcherEntries(Context c,SharedPreferences state)throws Exception {
  if(state.getBoolean("minimal_desktop_v1",false))return;
  PackageManager pm=c.getPackageManager();
  // Complete and verify the preferred HOME before retiring the fallback entry.
  home(c);
  for(String entry:ProvisionPolicy.hiddenLauncherEntries()) {
   ComponentName component=ComponentName.unflattenFromString(entry);
   if(component==null||HOME.equals(component.getPackageName()))throw new SecurityException("Invalid hidden entry");
   try {pm.getActivityInfo(component,PackageManager.MATCH_DISABLED_COMPONENTS);}
   catch(PackageManager.NameNotFoundException absent){continue;}
   pm.setComponentEnabledSetting(component,PackageManager.COMPONENT_ENABLED_STATE_DISABLED,PackageManager.DONT_KILL_APP);
   if(pm.getComponentEnabledSetting(component)!=PackageManager.COMPONENT_ENABLED_STATE_DISABLED)throw new IllegalStateException("Launcher entry state not retained: "+entry);
  }
  if(!state.edit().putBoolean("minimal_desktop_v1",true).commit())throw new IllegalStateException("Desktop state not committed");
 }
 private static void publishWallpapers(Context c)throws Exception {
  File[] originals=new File("/system/media/wallpapers").listFiles();
  if(originals==null)throw new IllegalStateException("Bundled wallpaper directory unavailable");
  Uri collection=MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
  String relative="Pictures/Wallpapers/";
  for(File source:originals) {
   if(!source.isFile()||!source.getName().endsWith(".jpg"))continue;
   try(Cursor found=c.getContentResolver().query(collection,new String[]{MediaStore.Images.Media._ID,MediaStore.Images.Media.IS_PENDING,MediaStore.Images.Media.OWNER_PACKAGE_NAME},
       MediaStore.Images.Media.RELATIVE_PATH+"=? AND "+MediaStore.Images.Media.DISPLAY_NAME+"=?",
       new String[]{relative,source.getName()},null)) {
    if(found==null)throw new IllegalStateException("MediaStore unavailable");
    if(found.moveToFirst()) {
     if(found.getInt(1)==0)continue;
     if(!c.getPackageName().equals(found.getString(2)))continue;
     // Recover only our own unpublished row after an interrupted first copy.
     Uri abandoned=android.content.ContentUris.withAppendedId(collection,found.getLong(0));
     c.getContentResolver().delete(abandoned,null,null);
    }
   }
   ContentValues values=new ContentValues();values.put(MediaStore.Images.Media.DISPLAY_NAME,source.getName());
   values.put(MediaStore.Images.Media.MIME_TYPE,"image/jpeg");values.put(MediaStore.Images.Media.RELATIVE_PATH,relative);
   values.put(MediaStore.Images.Media.IS_PENDING,1);
   Uri created=c.getContentResolver().insert(collection,values);
   if(created==null)throw new IllegalStateException("Wallpaper insert refused");
   boolean committed=false;
   try {
    MessageDigest original=MessageDigest.getInstance("SHA-256"),actual=MessageDigest.getInstance("SHA-256");
    try(FileInputStream input=new FileInputStream(source);OutputStream output=c.getContentResolver().openOutputStream(created,"w")) {
     if(output==null)throw new IllegalStateException("Wallpaper output unavailable");
     byte[] buffer=new byte[65536];for(int n;(n=input.read(buffer))>0;){original.update(buffer,0,n);output.write(buffer,0,n);}
    }
    try(java.io.InputStream input=c.getContentResolver().openInputStream(created)) {
     if(input==null)throw new IllegalStateException("Wallpaper readback unavailable");
     byte[] buffer=new byte[65536];for(int n;(n=input.read(buffer))>0;)actual.update(buffer,0,n);
    }
    if(!MessageDigest.isEqual(original.digest(),actual.digest()))throw new IllegalStateException("Wallpaper hash mismatch");
    values.clear();values.put(MediaStore.Images.Media.IS_PENDING,0);
    if(c.getContentResolver().update(created,values,null,null)!=1)throw new IllegalStateException("Wallpaper publish refused");
    committed=true;
   } finally {if(!committed)c.getContentResolver().delete(created,null,null);}
  }
 }
 private static void configure(Context c)throws Exception {
  SharedPreferences state=c.getSharedPreferences("roc_defaults_v1",Context.MODE_PRIVATE);
  // Only an explicit, verified predecessor migration may suppress fresh setup.
  boolean fresh=ProvisionPolicy.fresh(state.getBoolean("complete",false),Settings.Global.getInt(c.getContentResolver(),"roc_factory_legacy_complete",0)==1);
  if(fresh) {
   checkKeyboard(c);
   secure(c,Settings.Secure.ENABLED_INPUT_METHODS,ProvisionPolicy.addComponent(Settings.Secure.getString(c.getContentResolver(),Settings.Secure.ENABLED_INPUT_METHODS),IME));
   secure(c,Settings.Secure.DEFAULT_INPUT_METHOD,IME);
   secure(c,"show_ime_with_hard_keyboard","1");
   home(c);
   secure(c,Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,ProvisionPolicy.addComponent(Settings.Secure.getString(c.getContentResolver(),Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES),NAV));
   secure(c,Settings.Secure.ACCESSIBILITY_ENABLED,"1");
   global(c,Settings.Global.DEVICE_PROVISIONED,"1");secure(c,Settings.Secure.USER_SETUP_COMPLETE,"1");
  }
  if(ProvisionPolicy.reservedName(Settings.Global.getString(c.getContentResolver(),"device_name")))global(c,"device_name","ROC OS");
  if(ProvisionPolicy.reservedName(Settings.Secure.getString(c.getContentResolver(),"bluetooth_name")))secure(c,"bluetooth_name","ROC OS");
  networkDefaults(c);
  launcherEntries(c,state);
  if(!state.edit().putBoolean("complete",true).commit())throw new IllegalStateException("Completion state not committed");
  try {publishWallpapers(c);} catch(Exception e){Log.w(TAG,"Wallpaper publication deferred until next boot",e);}
  Log.i(TAG,"Defaults complete; mode="+(fresh?"fresh":"preserve-existing")+" uid="+Process.myUid());
 }
}
