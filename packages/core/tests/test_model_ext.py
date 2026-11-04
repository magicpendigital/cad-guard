import ezdxf


def test_model_features_modelspace_layers(synthetic):
    modelspace = ezdxf.readfile(synthetic / "model_features.dxf").modelspace()
    assert all(entity.dxf.layer != "0" for entity in modelspace)
    wipeouts = list(modelspace.query("WIPEOUT"))
    assert wipeouts
    assert all(entity.dxf.layer == "FN-PART-OUTL" for entity in wipeouts)
