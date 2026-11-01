import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.Method;
import com.android.tools.smali.dexlib2.iface.Field;
import com.android.tools.smali.dexlib2.iface.instruction.Instruction;
import com.android.tools.smali.dexlib2.iface.instruction.ReferenceInstruction;
import com.android.tools.smali.dexlib2.iface.reference.MethodReference;
import com.android.tools.smali.dexlib2.iface.reference.FieldReference;
import com.android.tools.smali.dexlib2.iface.reference.Reference;
import java.io.File;
import java.util.*;

/** Read-only method/field linkage screen, not a substitute for runtime testing. */
public final class FrameworkApiAudit {
    private static final Map<String,ClassDef> framework = new HashMap<>();
    private static String methodKey(MethodReference m) {
        return m.getName()+m.getParameterTypes().toString()+m.getReturnType();
    }
    private static boolean methodExists(String owner, MethodReference m, Set<String> seen) {
        if (!seen.add(owner)) return false;
        ClassDef c=framework.get(owner);
        if(c==null) return false;
        for(Method candidate:c.getMethods()) if(methodKey(candidate).equals(methodKey(m))) return true;
        if(m.getName().equals("<init>")) return false;
        if(c.getSuperclass()!=null && methodExists(c.getSuperclass(),m,seen)) return true;
        for(String i:c.getInterfaces()) if(methodExists(i,m,seen)) return true;
        return false;
    }
    private static boolean fieldExists(String owner, FieldReference f, Set<String> seen) {
        if(!seen.add(owner)) return false;
        ClassDef c=framework.get(owner);
        if(c==null) return false;
        List<Field> fields=new ArrayList<>();
        for(Field candidate:c.getStaticFields()) fields.add(candidate);
        for(Field candidate:c.getInstanceFields()) fields.add(candidate);
        for(Field candidate:fields) if(candidate.getName().equals(f.getName()) && candidate.getType().equals(f.getType())) return true;
        if(c.getSuperclass()!=null && fieldExists(c.getSuperclass(),f,seen)) return true;
        for(String i:c.getInterfaces()) if(fieldExists(i,f,seen)) return true;
        return false;
    }
    private static List<ClassDef> classes(String file) throws Exception {
        List<ClassDef> result=new ArrayList<>();
        com.android.tools.smali.dexlib2.iface.MultiDexContainer<?> container=
                DexFileFactory.loadDexContainer(new File(file),Opcodes.forApi(29));
        for(String entry:container.getDexEntryNames()) result.addAll(container.getEntry(entry).getDexFile().getClasses());
        return result;
    }
    public static void main(String[] args) throws Exception {
        if(Runtime.getRuntime().availableProcessors()!=1) throw new IllegalStateException("One worker required");
        for(String jar:args[0].split(":")) for(ClassDef c:classes(jar)) framework.put(c.getType(),c);
        for(int index=1;index<args.length;index++) {
            Set<String> missing=new TreeSet<>();
            List<ClassDef> appClasses=classes(args[index]);
            Set<String> ownClasses=new HashSet<>();
            for(ClassDef c:appClasses) ownClasses.add(c.getType());
            for(ClassDef c:appClasses) for(Method m:c.getMethods()) {
                if(m.getImplementation()==null) continue;
                for(Instruction instruction:m.getImplementation().getInstructions()) {
                    if(!(instruction instanceof ReferenceInstruction)) continue;
                    Reference reference=((ReferenceInstruction)instruction).getReference();
                    String owner=reference instanceof MethodReference ? ((MethodReference)reference).getDefiningClass()
                        : reference instanceof FieldReference ? ((FieldReference)reference).getDefiningClass() : "";
                    if(!framework.containsKey(owner)) {
                        if((owner.startsWith("Landroid/") || owner.startsWith("Lcom/android/internal/"))
                                && !ownClasses.contains(owner)) missing.add("CLASS "+owner);
                        continue;
                    }
                    if(reference instanceof MethodReference && !methodExists(owner,(MethodReference)reference,new HashSet<>())) missing.add(reference.toString());
                    if(reference instanceof FieldReference && !fieldExists(owner,(FieldReference)reference,new HashSet<>())) missing.add(reference.toString());
                }
            }
            System.out.println("APK="+new File(args[index]).getName()+" UNRESOLVED="+missing.size());
            for(String value:missing) System.out.println("MISSING="+value);
        }
    }
}
