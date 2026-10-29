import brut.androlib.src.SmaliBuilder;
import brut.directory.ExtFile;
import com.android.tools.smali.baksmali.Baksmali;
import com.android.tools.smali.baksmali.BaksmaliOptions;
import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.iface.DexFile;
import java.io.File;

/** One-worker assembler/disassembler for the pinned delivered framework. */
public final class FrameworkDexTool {
    public static void main(String[] args) throws Exception {
        if (Runtime.getRuntime().availableProcessors() != 1) {
            throw new IllegalStateException("Assembler must see exactly one CPU");
        }
        if (args[0].equals("find")) {
            com.android.tools.smali.dexlib2.iface.MultiDexContainer<?> container =
                    DexFileFactory.loadDexContainer(new File(args[1]), Opcodes.forApi(29));
            for (String entry : container.getDexEntryNames()) {
                for (com.android.tools.smali.dexlib2.iface.ClassDef definition : container.getEntry(entry).getDexFile().getClasses()) {
                    if (definition.getType().equals(args[2])) System.out.println("CLASS_ENTRY=" + entry);
                }
            }
        } else if (args[0].equals("disassemble")) {
            DexFile dex = DexFileFactory.loadDexContainer(new File(args[1]), Opcodes.forApi(29))
                    .getEntry(args[2]).getDexFile();
            BaksmaliOptions options = new BaksmaliOptions();
            options.apiLevel = 29;
            if (!Baksmali.disassembleDexFile(dex, new File(args[3]), 1, options)) {
                throw new IllegalStateException("disassembly failed");
            }
        } else if (args[0].equals("assemble")) {
            SmaliBuilder.build(new ExtFile(args[1]), new File(args[2]), 29);
        } else throw new IllegalArgumentException("Unknown operation");
    }
}
