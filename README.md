# 日本全国・複数系列バブルマップ

緯度・経度を含む縦持ちCSVから、複数のデータ系列を重ねて見られる日本全国のバブルマップを生成するPython 3.11以上向けプロジェクトです。Foliumで操作可能なHTML、GeoPandasとMatplotlibで資料・論文向けのPNG、PDF、SVGを同時に作成します。

## セットアップ

Python 3.11以上が必要です。Windows PowerShellでは次のように実行します。

~~~powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m src.make_all
~~~

macOS/Linuxでは、仮想環境を有効化した後に同じく pip install -r requirements.txt と python -m src.make_all を実行してください。

## 入力CSV

CSVは縦持ち形式で、次の必須列を持ちます。

| 列 | 内容 |
| --- | --- |
| name | 地点名。空欄不可 |
| latitude | 緯度（-90から90） |
| longitude | 経度（-180から180） |
| dataset | 系列名。空欄不可 |
| value | 数値 |

unit と description は任意です。存在しないときは空文字列として扱います。CSV例は data/points.csv にあります。入力ファイルは変更しません。

読み込み時に必須列、空欄、数値変換、緯度・経度の範囲、有限値、完全重複行を検証します。不正なデータは除外せず、CSV行番号・列名・値を含むエラーで停止します。負値はバブル計算時に入力エラーです。

## 設定

config.yaml から入力、出力、地図、バブル、静止画の設定を変更できます。設定ファイル中の相対パスは、その設定ファイルの場所を基準に解決します。

- data_validation.duplicates は error（既定）、first、sum から選べます。完全重複を検出すると警告し、errorは停止、firstは先頭行のみ採用、sumは完全重複の値を合算します。
- bubble.scaling は sqrt（既定）、linear、log から選べます。sqrtは値の平方根で半径を決めるため、見た目の円面積が値に比例しやすい方式です。logは大きな値の差を圧縮します。
- bubble.zero_value は minimum（最小半径）または hide（描画しない）です。
- bubble.normalize.mode は global または per_dataset です。globalは全系列で最大値を共有するため、系列間の絶対値を比較したい場合に適しています。per_datasetは各系列で最大値を取るため、系列ごとの相対的な分布を見やすくします。
- map.dataset_order に系列名を列挙すると重なり順を制御できます。CSVにあって設定にない系列は、コード変更なしで自動配色されます。
- static_map.show_grid、show_dataset_legend、show_size_legend は静止画の表示を切り替えます。

バブル半径は既定で、最大値に対する比率を平方根でスケールします。概念的には minimum_radius + (maximum_radius - minimum_radius) * sqrt(value / maximum_value) です。ゼロだけの系列もゼロ除算せず処理します。

## 実行

全成果物を生成します。

~~~powershell
python -m src.make_all
python -m src.make_all --config config.yaml
~~~

個別に生成します。

~~~powershell
python -m src.make_all --html-only
python -m src.make_all --static-only
~~~

入力CSVと出力先も上書きできます。

~~~powershell
python -m src.make_all --input data/another_points.csv --output output/sample
~~~

実行後、生成したすべての絶対パスを表示します。同名ファイルは安全に上書きされ、出力先がなければ作成します。

## 出力と使い分け

output/japan_bubble_map.html は拡大・縮小、系列ごとの表示切替、ホバー時の値表示、クリック時の詳細表を提供します。同一座標の系列は半透明に重ね、LayerControlで個別に確認できます。地図内の凡例には系列色、サイズ目安、単位を表示します。

output/japan_bubble_map.png は300 dpiのラスター画像です。output/japan_bubble_map.pdf と output/japan_bubble_map.svg はベクター形式で、資料や論文のレイアウト編集に向きます。静止画には背景地図、輪郭、軸、タイトル、系列凡例、サイズ凡例を含めます。

## 背景地図とライセンス

静止画は、まず任意の data/geo/japan.geojson を利用します。未配置ならGeoPandas 0.14系に同梱される Natural Earth low-resolution データの日本ポリゴンを使うため、通常の実行でネット接続を必要としません。Natural Earthのデータはパブリックドメインです。出典: Natural Earth, naturalearthdata.com。

より詳細な行政区域が必要なら、ライセンスを確認した日本のGeoJSONを data/geo/japan.geojson に置いてください。

## 日本語フォント

Noto Sans CJK JP、Noto Sans JP、IPAexGothic、Yu Gothic、Meiryoを順に探索します。見つからない環境でも処理は継続しますが、日本語ラベルが正しく表示されないことがあるため、いずれかの日本語フォントをインストールしてください。

## テストとトラブルシューティング

~~~powershell
pytest
~~~

- CSVの検証エラー: 表示されたCSV行・列・値を修正してください。先頭行はヘッダーなので、最初のデータは行2です。
- 背景地図エラー: requirements.txtに従い geopandas 0.14系をインストールするか、data/geo/japan.geojson を配置してください。
- HTMLの地図タイルが表示されない: HTMLの操作には地図タイルを読み込むネット接続が必要です。生成そのものはオフラインで可能です。
- 文字化け: input.encodingをCSVの文字コードに合わせてください。Excel由来のCSVでは cp932 が必要な場合があります。

新しい系列を追加するには、CSVへdataset名を持つ行を追加するだけです。datasets設定を追加するとラベル・色・初期表示・透明度を明示的に指定できます。
