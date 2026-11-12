// SPDX-License-Identifier: Apache-2.0
package com.roc.os.provisioning;
public final class ProvisionPolicy {
 private ProvisionPolicy() {}
 public static boolean supported(String device,String profile,String round,int user) {
  return "rgsp".equals(device)&&"rg34xxsp".equals(profile)&&"2".equals(round)&&user==0;
 }
 public static boolean fresh(boolean done,boolean legacyAccepted) {
  return !done && !legacyAccepted;
 }
 public static boolean reservedName(String s) {
  return s==null||s.isEmpty()||"null".equals(s)||"RGSP H700".equals(s)||"RGSP_H700".equals(s)||"H700 Android USB".equals(s);
 }
 public static String addComponent(String existing,String component) {
  if(existing==null||existing.isEmpty()||"null".equals(existing))return component;
  for(String s:existing.split(":"))if(s.split(";",2)[0].equals(component))return existing;
  return existing+":"+component;
 }
 public static String[] hiddenLauncherEntries() {
  // Activities only: never disable WebView, ContactsProvider or whole packages.
  return new String[]{
   "com.roc.rgsp.launcher/.MainActivity",
   "com.android.quicksearchbox/.SearchActivity",
   "org.chromium.webview_shell/.WebViewBrowserActivity",
   "com.android.email/.activity.Welcome",
   "com.android.traceur/.MainActivity",
   "com.android.contacts/.activities.PeopleActivity"
  };
 }
}
