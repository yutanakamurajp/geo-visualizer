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

### フローCSV（ディレクションプロット）

ノード間の移動量を重ねるときは data/flows.csv のような縦持ちCSVを用意し、明示的に `--flows` で渡します。`input.flow_csv_path` は標準のサンプル位置を記録する設定であり、後方互換性のため `--flows` を省略した実行は従来どおりバブルのみを生成します。

| 列 | 必須 | 内容 |
| --- | --- | --- |
| from_name | はい | 始点ノード名。points.csv の name を参照し、空欄不可 |
| to_name | はい | 終点ノード名。points.csv の name を参照し、空欄不可 |
| dataset | はい | フロー系列名。空欄不可 |
| value | はい | 移動量（有限の数値） |
| unit | いいえ | 単位 |
| description | いいえ | 説明 |

`value > 0` は `from_name → to_name`、`value < 0` は絶対値で太さを決めて `to_name → from_name` に反転します。ゼロは既定で描画しません。フローのツールチップとポップアップには、入力上の始点・終点、入力値、実際の描画方向、単位を併記します。

フローの参照先がノードCSVにない場合、`value` が数値・有限値でない場合、完全重複行、または同じノード名に異なる座標がある場合も、該当CSV行・列・値を示すエラーで停止します。完全重複行は `data_validation.duplicates` の `error` / `first` / `sum` を地点CSVと共有します。

## 設定

config.yaml から入力、出力、地図、バブル、静止画の設定を変更できます。設定ファイル中の相対パスは、その設定ファイルの場所を基準に解決します。

- data_validation.duplicates は error（既定）、first、sum から選べます。完全重複を検出すると警告し、errorは停止、firstは先頭行のみ採用、sumは完全重複の値を合算します。
- bubble.scaling は sqrt（既定）、linear、log から選べます。sqrtは値の平方根で半径を決めるため、見た目の円面積が値に比例しやすい方式です。logは大きな値の差を圧縮します。
- bubble.zero_value は minimum（最小半径）または hide（描画しない）です。
- bubble.normalize.maximum(任意、global のときだけ)を数値で指定すると、データの最大値ではなくこの値で正規化します。時刻ごとに分けた複数の地図で、同じ値を同じ大きさに描くときに使います。超える値は最大半径です。per_dataset のときは {系列名: 最大値} の対応で系列ごとに指定できます(書かない系列はデータの最大値)。flow.normalize.maximum も同じ意味です。
- bubble.normalize.mode は global または per_dataset です。globalは全系列で最大値を共有するため、系列間の絶対値を比較したい場合に適しています。per_datasetは各系列で最大値を取るため、系列ごとの相対的な分布を見やすくします。
- flow.enabled はフロー描画の有効・無効、flow.minimum_width / maximum_width は線幅、flow.scaling は sqrt / linear / log、flow.zero_value は hide / minimum を設定します。正負を問わず絶対値で正規化します。
- flow.normalize.mode の global / per_dataset はバブルと同じ意味です。flow.opacity、flow.arrow.enabled、flow.arrow.size、flow.curvature（同じノード対の複数フローを少し曲げる量）も設定できます。
- フロー線の色は `datasets.<フロー系列名>.color` で設定します。未設定のフロー系列はバブルと同じ自動配色規則を使用します。datasets の label / visible もフローの凡例・初期表示に反映されます。
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
python -m src.make_all --nodes data/points.csv --flows data/flows.csv
python -m src.make_all --nodes data/points.csv --flows data/flows.csv --output output/flow_sample
python -m src.make_all --html-only --nodes data/points.csv --flows data/flows.csv
python -m src.make_all --static-only --nodes data/points.csv --flows data/flows.csv
~~~

実行後、生成したすべての絶対パスを表示します。同名ファイルは安全に上書きされ、出力先がなければ作成します。

## 出力と使い分け

output/japan_bubble_map.html は拡大・縮小、系列ごとの表示切替、ホバー時の値表示、クリック時の詳細表を提供します。同一座標の系列は半透明に重ね、LayerControlで個別に確認できます。フローを指定した場合はフロー系列ごとのレイヤー、太さに比例した曲線、終端矢印を追加し、ホバーとクリックで方向情報を確認できます。地点名・説明・単位などCSV由来のHTMLはエスケープして出力します。

output/japan_bubble_map.png は300 dpiのラスター画像です。output/japan_bubble_map.pdf と output/japan_bubble_map.svg はベクター形式で、資料や論文のレイアウト編集に向きます。静止画には背景地図、輪郭、軸、タイトル、バブル系列・サイズ凡例を含め、フローがあればMatplotlib矢印とフロー系列凡例も重ねます。

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
