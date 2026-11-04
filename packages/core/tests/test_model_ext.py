import json

from cadguard.dxf_reader import read_dxf
from cadguard.model import DrawingModel


def test_legacy_json_defaults():
    model = DrawingModel.model_validate(json.loads('{"schema":"cg.drawing/1","layers":[{"name":"0"}],"entities":[{"handle":"1","type":"LINE","layer":"0"}]}'))
    assert model.stats is None and model.blocks == [] and model.styles == [] and model.dim_styles == []
    assert not model.layers[0].xref_dependent and model.layers[0].xref_name is None
    assert model.entities[0].color is None and model.entities[0].lineweight is None and model.entities[0].true_color is None


def test_feature_statistics(synthetic):
    model = read_dxf(synthetic / "model_features.dxf")
    stats = model.stats
    assert stats.source == "ezdxf" and stats.layers_xref_dependent == 2
    assert stats.max_block_depth == 2 and stats.blocks_anonymous >= 1
    assert {"shx", "ttf"} <= {style.font_kind for style in model.styles}
    assert stats.modelspace.wipeout == 1 and stats.modelspace.image == 1
    assert stats.modelspace.dim_text_override == 1
    assert stats.modelspace.color_override >= 1 and stats.modelspace.lineweight_override >= 1
    assert stats.blocks.entities > 0 and len(stats.blocks.by_layer) >= 2


def test_clean_statistics(synthetic):
    model = read_dxf(synthetic / "ok_sheet.dxf")
    assert model.stats is not None and model.stats.layers_xref_dependent == 0
