"""Keep RGSP LAN debugging eligible after an Internet-validation failure."""
import argparse,hashlib,json
from pathlib import Path

REL='frameworks/opt/net/wifi/service/java/com/android/server/wifi/ClientModeImpl.java'
BEFORE='43bcf5ff2a7b546085c30f8e2198861469de932c20ba6b8b31c693b88050f08e'
OLD='''                                if (mWifiConfigManager.getLastSelectedNetwork() != config.networkId
                                        && !config.noInternetAccessExpected) {'''
NEW='''                                // This Wi-Fi-only handheld also uses local WLAN for debugging.
                                // Failed WAN validation must not blacklist a working LAN for 10 min.
                                // Keep validation reports and explicit user rejection unchanged.
                                final boolean keepLocalWlan = "rgsp".equals(android.os.Build.DEVICE)
                                        && !mContext.getPackageManager().hasSystemFeature(
                                                android.content.pm.PackageManager.FEATURE_TELEPHONY);
                                if (keepLocalWlan) {
                                    Log.i(TAG, "RGSP: keep local WLAN eligible after WAN validation failure");
                                }
                                if (!keepLocalWlan
                                        && mWifiConfigManager.getLastSelectedNetwork() != config.networkId
                                        && !config.noInternetAccessExpected) {'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    path=a.source/REL;text=path.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE or base.count(OLD)!=1:
        raise SystemExit('Unrecognized Wi-Fi source changes; preserved')
    result=base.replace(OLD,NEW,1)
    if text!=result:path.write_text(result)
    (a.source/'out/rgsp-local-wifi-inputs.json').write_text(json.dumps({REL:hashlib.sha256(result.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_LOCAL_WLAN_RECONNECT_POLICY_PREPARED')

if __name__=='__main__':main()
