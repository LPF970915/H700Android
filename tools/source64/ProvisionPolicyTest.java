package com.roc.os.provisioning;
public class ProvisionPolicyTest {
 public static void main(String[] a) {
  if(!ProvisionPolicy.supported("rgsp","rg34xxsp","2",0)||ProvisionPolicy.supported("rgsp","rg34xxsp","2",10)||ProvisionPolicy.supported("other","rg34xxsp","2",0))throw new AssertionError("guard");
  if(!ProvisionPolicy.fresh(false,false)||ProvisionPolicy.fresh(true,false)||ProvisionPolicy.fresh(false,true)||!ProvisionPolicy.fresh(false,false))throw new AssertionError("fresh/retry/adopt");
  if(!ProvisionPolicy.reservedName(null)||!ProvisionPolicy.reservedName("RGSP H700")||ProvisionPolicy.reservedName("my device")||ProvisionPolicy.reservedName("ROC OS"))throw new AssertionError("name preservation");
  if(!"ime;42".equals(ProvisionPolicy.addComponent("ime;42","ime"))||!"one:two".equals(ProvisionPolicy.addComponent("one","two"))||!"two".equals(ProvisionPolicy.addComponent("null","two")))throw new AssertionError("preserve components");
  System.out.println("PROVISION_GUARD_FRESH_RETRY_ADOPT_CUSTOM_NAMES_COMPONENTS_PASS");
 }
}
