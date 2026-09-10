# Expression score investigation

Five live raw output samples are saved in `evidence/2026-09-10-expression-scores/raw.log`. They contain negative logits (range across samples approximately -1.51 to 0.51), not probabilities. The archive's `is_softmax=false` correctly instructs ClassificationParser to apply softmax once. A duplicate softmax was suspected but ruled out; no normalization override or score inflation was introduced.

The pipeline uses BGR888i input, FrameCropper and ParsingNeuralNetwork as in Luxonis's `neural-networks/face-detection/emotion-recognition/main.py` reference. These checks do not prove model accuracy or rule out every crop/model limitation. The cause of weak class separation is not established.

The overlay now shows the leading expression candidate and marks scores below 0.50 as low confidence instead of hiding the candidate behind `uncertain`. This is a display improvement, not a model accuracy fix. Optional `OAK_WEBCAM_EXPRESSION_DIAGNOSTICS=1` logs only the first five raw classification vectors per process for troubleshooting; normally disabled.

The five raw vectors yield top softmax scores 0.1981, 0.2208, 0.2295, 0.1999 and 0.2309. All ten Python tests and `git diff --check` passed. The updated app built and started on the OAK with mirror-text enabled and diagnostics disabled; the host requested a 3840×2160 stream at 17:01:05 UTC (`updated.log` beside the raw evidence). This startup evidence does not independently verify the final rendered panel in Google Meet.
