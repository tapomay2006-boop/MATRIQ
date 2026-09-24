"""The Siamese model itself: shared weights, batched pair scoring, the
training loop, and the checkpoint round-trip through the reranker service.

Needs torch, transformers and the pretrained backbone in the local Hugging
Face cache - none of which the default suite has - so every test here skips
rather than fails when they are absent. `HF_HUB_OFFLINE` is set so a missing
backbone is a skip in milliseconds, not a download attempt.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from app.logic.siamese import (  # noqa: E402
    ContrastiveLoss,
    SiameseConfig,
    SiameseModel,
    best_f1_threshold,
)
from app.training.pairs import Pair  # noqa: E402
from app.training.train_siamese import TrainingConfig, train  # noqa: E402

BACKBONE = os.getenv("SIAMESE_TEST_BACKBONE", "sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture(scope="module")
def model():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        return SiameseModel(SiameseConfig(backbone=BACKBONE, max_length=32), device="cpu")
    except Exception as exc:  # noqa: BLE001 - the backbone is not cached here
        pytest.skip(f"backbone {BACKBONE} not available offline: {exc}")


def test_both_sides_go_through_the_same_weights(model):
    """Symmetric by construction: there is one encoder, so score(a, b) == score(b, a)."""
    ab = model.pair_scores("V BELT C 120", ["V-BELT C-120"])[0]
    ba = model.pair_scores("V-BELT C-120", ["V BELT C 120"])[0]
    assert ab == pytest.approx(ba, abs=1e-5)
    same = model.encode(["BALL BEARING 6205", "BALL BEARING 6205"])
    assert np.allclose(same[0], same[1])


def test_there_is_exactly_one_encoder_and_one_set_of_weights(model):
    """Not a convention - a structural fact. The model owns ONE module; the
    training loop and `pair_scores` push both sides through `model.module`.
    There is no second parameter set that could drift."""
    import inspect

    from app.training import train_siamese

    modules = [m for m in vars(model).values() if isinstance(m, torch.nn.Module)]
    assert modules == [model.module]
    source = inspect.getsource(train_siamese.train)
    assert 'a = module(tq["input_ids"], tq["attention_mask"])' in source
    assert 'b = module(tc["input_ids"], tc["attention_mask"])' in source
    assert "module_b" not in source and "encoder_b" not in source


def test_pair_scores_are_one_batched_forward(model, monkeypatch):
    calls: list[int] = []
    original = model.module.forward

    def counting(input_ids, attention_mask):
        calls.append(int(input_ids.shape[0]))
        return original(input_ids, attention_mask)

    monkeypatch.setattr(model.module, "forward", counting)
    model.pair_scores("gate valve 2 inch", [f"gate valve {i} inch" for i in range(20)])
    assert calls == [21]  # the query plus twenty candidates, once


def test_training_changes_the_trainable_weights(model, tmp_path):
    """pairs -> forward -> loss -> backward -> optimizer.step(): the weights
    after are not the weights before, in the head AND in the backbone."""
    pairs = [
        Pair("V BELT C 120", "V-BELT C-120", 1), Pair("BEARING 6205", "BALL BEARING 6205", 1),
        Pair("V BELT C 120", "HEX BOLT M10 X 50", 0), Pair("BEARING 6205", "SAFETY SHOE", 0),
    ]
    before_head = None
    before_backbone = None

    from app.logic import siamese as siamese_module

    real_build = siamese_module.SiameseEncoder.build

    def capturing(config, **kwargs):
        nonlocal before_head, before_backbone
        module = real_build(config, **kwargs)
        before_head = [p.detach().clone() for p in module.head.parameters()]
        before_backbone = [p.detach().clone() for p in module.backbone.parameters()]
        return module

    siamese_module.SiameseEncoder.build = staticmethod(capturing)
    try:
        train(
            pairs, pairs,
            TrainingConfig(
                output_dir=str(tmp_path / "w"), backbone=BACKBONE, epochs=1, batch_size=4,
                device="cpu", max_length=32, eval_batch_size=8, learning_rate=1e-4,
            ),
        )
    finally:
        siamese_module.SiameseEncoder.build = staticmethod(real_build)

    trained = SiameseModel.load(tmp_path / "w", device="cpu")
    after_head = list(trained.module.head.parameters())
    after_backbone = list(trained.module.backbone.parameters())
    assert any(not torch.equal(a, b.detach()) for a, b in zip(before_head, after_head, strict=True))
    assert any(
        not torch.equal(a, b.detach()) for a, b in zip(before_backbone, after_backbone, strict=True)
    )


def test_projections_are_unit_length_and_scores_are_in_range(model):
    vectors = model.encode(["a", "hex bolt m10", "gate valve 2 inch"])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    scores = model.pair_scores("gate valve", ["gate valve 2 inch", "office chair"])
    assert scores.shape == (2,)
    assert ((scores >= 0.0) & (scores <= 1.0)).all()
    assert model.pair_scores("x", []).shape == (0,)


def test_contrastive_loss_is_zero_when_already_correct():
    loss = ContrastiveLoss(margin=1.0)
    a = torch.nn.functional.normalize(torch.randn(4, 8), dim=-1)
    same = loss(a, a, torch.ones(4))
    assert float(same) == pytest.approx(0.0, abs=1e-6)
    far = loss(a, -a, torch.zeros(4))  # distance 2 > margin 1
    assert float(far) == pytest.approx(0.0, abs=1e-6)
    pulled = loss(a, -a, torch.ones(4))
    assert float(pulled) > 0.0


def test_best_f1_threshold_separates_a_separable_set():
    scores = np.array([0.95, 0.9, 0.85, 0.3, 0.2, 0.1])
    labels = np.array([1, 1, 1, 0, 0, 0])
    threshold, metrics = best_f1_threshold(scores, labels)
    assert 0.3 < threshold <= 0.85
    assert metrics["f1"] == 1.0


def test_training_saves_a_checkpoint_the_service_can_load(model, tmp_path):
    from app.config import settings
    from app.services import reranker as reranker_service

    pairs = [
        Pair("V BELT C 120", "V-BELT C-120", 1), Pair("V BELT C 120", "BELT V C120", 1),
        Pair("BEARING 6205", "BALL BEARING 6205", 1), Pair("HEX BOLT M10", "HEX BOLT M10 X 50", 1),
        Pair("V BELT C 120", "HEX BOLT M10 X 50", 0), Pair("V BELT C 120", "GATE VALVE 2 INCH", 0),
        Pair("BEARING 6205", "SAFETY SHOE SIZE 9", 0), Pair("HEX BOLT M10", "LED FLOOD LIGHT", 0),
    ]
    output = tmp_path / "ckpt"
    result = train(
        pairs, pairs,
        TrainingConfig(
            output_dir=str(output), backbone=BACKBONE, epochs=1, batch_size=4,
            freeze_backbone=True, device="cpu", max_length=32, eval_batch_size=8,
        ),
    )
    assert result.best_epoch == 1
    assert (output / "config.json").exists()
    assert (output / "head.pt").exists()
    assert (output / "backbone").is_dir()
    assert (output / "training_result.json").exists()

    loaded = SiameseModel.load(output, device="cpu")
    assert loaded.config.pair_threshold is not None
    assert loaded.pair_scores("V BELT C 120", ["V-BELT C-120", "HEX BOLT"]).shape == (2,)

    original = settings.siamese_model_path
    settings.siamese_model_path = str(output)
    try:
        reranker_service.set_reranker(None)
        loaded_reranker = reranker_service.get_reranker(refresh=True)
        assert loaded_reranker is not None
        status = reranker_service.status()
        assert status.available is True
        assert status.parameters > 0
        assert status.pair_threshold == loaded.config.pair_threshold
    finally:
        settings.siamese_model_path = original
        reranker_service.set_reranker(None)


def test_loading_a_missing_checkpoint_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        SiameseModel.load(tmp_path / "nothing-here")
