.class public final Lcom/overdevs/at4k/RgspLayout;
.super Ljava/lang/Object;

# Menu text uses the primary menu's 14sp; do not rewrite shared padding registers.
.method public static menuSp(I)J
    .locals 2
    const/16 p0, 0xe
    invoke-static {p0}, LB3/a;->E(I)J
    move-result-wide v0
    return-wide v0
.end method

# Match primary-menu text even when a dialog's Material style supplies its
# font size through a default argument. Preserve the original callback/style.
.method public static menuText(Ljava/lang/String;LZ/o;JJLM0/t;LM0/i;JLS0/i;JIZIILH0/I;LN/p;III)V
    .locals 2
    const/16 v0, 0xe
    invoke-static {v0}, LB3/a;->E(I)J
    move-result-wide v0
    move-wide/16 p4, v0
    and-int/lit8 p21, p21, -0x9
    invoke-static/range {p0 .. p21}, LK/L0;->b(Ljava/lang/String;LZ/o;JJLM0/t;LM0/i;JLS0/i;JIZIILH0/I;LN/p;III)V
    return-void
.end method

# App Manager's four fixed 100/120dp columns previously consumed the entire
# small-screen row, leaving its weighted application-name column zero width.
.method public static tableCell(LZ/o;F)LZ/o;
    .locals 2
    const/high16 v0, 0x42400000    # 48f
    cmpg-float v0, p1, v0
    if-ltz v0, :original
    const/high16 v0, 0x43000000    # 128f
    cmpl-float v0, p1, v0
    if-gtz v0, :original
    const/high16 p1, 0x42800000    # 64f
    :original
    invoke-static {p0, p1}, Landroidx/compose/foundation/layout/d;->n(LZ/o;F)LZ/o;
    move-result-object p0
    return-object p0
.end method

.method public static tableSpace(LZ/o;F)LZ/o;
    .locals 2
    const/high16 v0, 0x41000000    # 8f
    cmpl-float v0, p1, v0
    if-lez v0, :original
    const/high16 v0, 0x42200000    # 40f
    cmpl-float v0, p1, v0
    if-gtz v0, :original
    const/high16 p1, 0x41000000
    :original
    invoke-static {p0, p1}, Landroidx/compose/foundation/layout/d;->g(LZ/o;F)LZ/o;
    move-result-object p0
    return-object p0
.end method

# Existing menu rows only supplied key callbacks; expose the same onSelect as
# a real click action for accessibility, pointer input and D-pad activation.
.method public static menuClick(LZ/o;Lo4/a;)LZ/o;
    .locals 3
    const/4 v0, 0x1
    const/4 v1, 0x0
    const/4 v2, 0x2
    invoke-static {p0, v0, v1, p1, v2}, Landroidx/compose/foundation/a;->f(LZ/o;ZLjava/lang/String;Lo4/a;I)LZ/o;
    move-result-object p0
    return-object p0
.end method

# Lift the original scrolling app area, without changing row order or its scroll state.
.method public static liftApps(Landroid/content/Context;LZ/o;)LZ/o;
    .locals 2
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v0
    iget v0, v0, Landroid/content/res/Configuration;->screenHeightDp:I
    if-lez v0, :original
    const/16 v1, 0x258
    if-ge v0, v1, :original
    const/high16 v0, -0x3db00000    # -52.0f
    invoke-static {v0}, Landroidx/compose/foundation/layout/a;->g(F)LZ/o;
    move-result-object v0
    invoke-interface {p1, v0}, LZ/o;->i(LZ/o;)LZ/o;
    move-result-object p1
    :original
    return-object p1
.end method

# The toolbar shares the scroll container; retain its original screen position.
.method public static restoreToolbar(Landroid/content/Context;LZ/o;)LZ/o;
    .locals 2
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v0
    iget v0, v0, Landroid/content/res/Configuration;->screenHeightDp:I
    if-lez v0, :original
    const/16 v1, 0x258
    if-ge v0, v1, :original
    const/high16 v0, 0x42500000    # 52.0f
    invoke-static {v0}, Landroidx/compose/foundation/layout/a;->g(F)LZ/o;
    move-result-object v0
    invoke-interface {p1, v0}, LZ/o;->i(LZ/o;)LZ/o;
    move-result-object p1
    :original
    return-object p1
.end method
