# sousikifuyou.github.io

・自分用、勉強用です
・GitHubPagesに慣れるためのもの

## フォルダ構成

```
.
├── index.html                  トップページ（各ツールへのリンク）
├── README.md
└── tools/
    ├── html-editor/            HTML コードエディタ（PC 向け）
    │   └── lib/                CodeMirror ライブラリ
    ├── multi-tool/             自分用マルチツール（PC 向け、HTML 単体）
    └── ios/                    iPhone 向けツール
        ├── iphone-fft/         FFT解析
        ├── iphone-angle/       方位・水準器
        └── iphone-genshin-materials/  原神素材
            ├── genshin-data.json       自動生成データ（毎日更新）
            ├── sw.js                   アイコン画像のキャッシュ（サービスワーカー）
            └── scripts/                データ生成スクリプト
```

## 原神素材データの自動更新

`.github/workflows/update-genshin-data.yml` が毎日 06:17 (JST) に実行され、
npm で公開されている [genshin-db](https://github.com/theBowja/genshin-db) の最新版から
`tools/ios/iphone-genshin-materials/genshin-data.json` を生成し、変更があればコミットします。
Actions タブの「原神素材データ自動更新」から手動実行もできます。
