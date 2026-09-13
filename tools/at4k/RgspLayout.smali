.class public final Lcom/overdevs/at4k/RgspLayout;
.super Ljava/lang/Object;

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
