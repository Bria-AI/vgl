# Changelog

## [0.10.1](https://github.com/Bria-AI/vgl/compare/v0.10.0...v0.10.1) (2026-10-27)


### Bug Fixes

* ask once more for an invalid VGL reply, then raise it as a refusal ([#43](https://github.com/Bria-AI/vgl/issues/43)) ([f7d0803](https://github.com/Bria-AI/vgl/commit/f7d08034d0c5d7d8c91e5c84cac14a6fe30e3fea))
* exclude litellm 1.107.0, the compromised release ([#45](https://github.com/Bria-AI/vgl/issues/45)) ([8211c2c](https://github.com/Bria-AI/vgl/commit/8211c2cdbc4c1a2bd78b51e40ffbc8e6c751f6f8))

## [0.10.0](https://github.com/Bria-AI/vgl/compare/v0.9.0...v0.10.0) (2026-10-21)


### Features

* accept Refine in create() as well as modify() ([#40](https://github.com/Bria-AI/vgl/issues/40)) ([9f1c9a4](https://github.com/Bria-AI/vgl/commit/9f1c9a411d5f7c3c07a8df172da9128bf664933c))

## [0.9.0](https://github.com/Bria-AI/vgl/compare/v0.8.0...v0.9.0) (2026-10-20)


### Features

* raise ContentFilteredError on a blocked LLM reply instead of a TypeError ([#19](https://github.com/Bria-AI/vgl/issues/19)) ([301f497](https://github.com/Bria-AI/vgl/commit/301f49728cd33216dfea8d1271d457d43755124b))

## [0.8.0](https://github.com/Bria-AI/vgl/compare/v0.7.0...v0.8.0) (2026-10-20)


### Features

* use research's v2 expander prompt for thales generate ([#31](https://github.com/Bria-AI/vgl/issues/31)) ([5aaf3ec](https://github.com/Bria-AI/vgl/commit/5aaf3ec81f4fc195fa83213bda7617268f30eb52))

## [0.7.0](https://github.com/Bria-AI/vgl/compare/v0.6.0...v0.7.0) (2026-10-20)


### Features

* restore Refine, a VGL changed by a prompt with no image ([#28](https://github.com/Bria-AI/vgl/issues/28)) ([69a6c73](https://github.com/Bria-AI/vgl/commit/69a6c73ad953239dfe9478c6d22c7b6adce9f3c0))

## [0.6.0](https://github.com/Bria-AI/vgl/compare/v0.5.0...v0.6.0) (2026-10-19)


### Features

* **thales:** add Caption payload ([#25](https://github.com/Bria-AI/vgl/issues/25)) ([7ce2a5f](https://github.com/Bria-AI/vgl/commit/7ce2a5fbb5a8247b308de2df3a65b4ebe6b3479d))

## [0.5.0](https://github.com/Bria-AI/vgl/compare/v0.4.0...v0.5.0) (2026-10-18)


### Features

* final_prompt override in create ([#23](https://github.com/Bria-AI/vgl/issues/23)) ([9f1e163](https://github.com/Bria-AI/vgl/commit/9f1e163b1f0116b163435e466da34b7941bbc288))

## [0.4.0](https://github.com/Bria-AI/vgl/compare/v0.3.2...v0.4.0) (2026-10-18)


### Features

* **thales:** add Inspire payload ([#20](https://github.com/Bria-AI/vgl/issues/20)) ([2683ee1](https://github.com/Bria-AI/vgl/commit/2683ee1342f974716c307c65cd136af7ff0f86ff))

## [0.3.2](https://github.com/Bria-AI/vgl/compare/v0.3.1...v0.3.2) (2026-10-15)


### Bug Fixes

* send Gemini 3+ minimal thinking on Vertex too ([#9](https://github.com/Bria-AI/vgl/issues/9)) ([f0643a7](https://github.com/Bria-AI/vgl/commit/f0643a7fb410be7881eadb8daf9edfae051b55f3))

## [0.3.1](https://github.com/Bria-AI/vgl/compare/v0.3.0...v0.3.1) (2026-10-15)


### Bug Fixes

* send the seed to Gemini on AI Studio ([#15](https://github.com/Bria-AI/vgl/issues/15)) ([785edad](https://github.com/Bria-AI/vgl/commit/785edadfe74b1f089e53435c66ce2ddab63b0e01))

## [0.3.0](https://github.com/Bria-AI/vgl/compare/v0.2.0...v0.3.0) (2026-10-14)


### Features

* import bria-vgl as bria_vgl ([#13](https://github.com/Bria-AI/vgl/issues/13)) ([97759e5](https://github.com/Bria-AI/vgl/commit/97759e5f6bb25f2be50f515646530f3adfe05b26))

## [0.2.0](https://github.com/Bria-AI/vgl/compare/v0.1.0...v0.2.0) (2026-10-13)


### Features

* generation overrides on vgl.create ([#10](https://github.com/Bria-AI/vgl/issues/10)) ([817db48](https://github.com/Bria-AI/vgl/commit/817db4860d4e97b6c2dbba3cc5e28dae49788d79))

## 0.1.0 (2026-10-13)


### Features

* in the beginning there was a prompt, and it was unstructured ([b10a95f](https://github.com/Bria-AI/vgl/commit/b10a95f1fc801108a38984428ea83929b9f743fd))


### Bug Fixes

* make AI Studio calls work on Gemini 3+ ([#8](https://github.com/Bria-AI/vgl/issues/8)) ([6153416](https://github.com/Bria-AI/vgl/commit/6153416f1ff4645f9613f59285fc7b09f607d3ef))


### Documentation

* use full GitHub URLs in the README so links work on PyPI ([#6](https://github.com/Bria-AI/vgl/issues/6)) ([94d85b0](https://github.com/Bria-AI/vgl/commit/94d85b08485a5a82e3de4368365eda2b4b6acc26))
