# Speedometer textures (optional)

By default the speedometer uses the game's own 3D digits (from your Race.szs)
and the KM/H label in assets/speedometer/. To change how it looks, put any of
these textures here and run `tools/pack_assets.py` again:

    som_d_number_3d_00.tpl ... som_d_number_3d_09.tpl
    som_d_number_3d_coron.tpl   the dot
    som_d_none.tpl              an empty digit
    speed.tpl                   the KM/H label

These are the texture names of Pulsar's speedometer. Recolour packs made for
CTGP's speedometer use different files and layouts, so they don't drop in
directly.
