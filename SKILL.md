---
name: showroom-3d-walk
description: Tạo 1 showroom / cửa hàng / phòng 3D mới trên web nhìn như ảnh chụp, cuộn là đi bộ quanh tiệm như khách bước vào (kiểu finely-crafted.com). Blender dựng cảnh bằng script, đồ scan Poly Haven CC0 + model AI cho món chính, Cycles bake ánh sáng, web WebGL (three.js) vẽ lại phòng mỗi khung đúng độ phân giải màn hình, 60 khung/giây, sàn và gương phản chiếu, hotspot bấm xem món đồ và giá, caption theo đoạn, deploy Vercel. Có 2 cỡ - phòng nhỏ (bake màu vào texture) và phòng lớn (lightmap + texture lặp, ánh sáng theo đỉnh cho quần áo). Duyệt concept, món chính, ảnh Cycles, bản web local trước khi đi tiếp; có script đo khung/giây và chụp kiểm tra. Bước tuỳ chọn - user gửi link web mẫu thì phân tích nó bằng REA trước. Dùng khi user nói "showroom 3D", "làm showroom 3D", "cửa hàng 3D", "tiệm 3D", "phòng 3D nhìn thật", "phòng mẫu 3D", "website cuộn là đi bộ trong phòng", "web 3D giống finely crafted", "web 3D nhìn giả quá", "dựng lại showroom như Bumatech", hoặc gửi link 1 web 3D muốn làm bản riêng nhìn thật như vậy.
---

# Showroom 3D Walk

Tạo showroom 3D mới, cuộn là đi bộ quanh tiệm. Ví dụ đã làm:
- Hollow Oak Lounge (phòng nhỏ). **Bản chuẩn, style Thành chốt 17/10/2026: https://hollow-oak-lounge-3d.vercel.app**
- Tiệm streetwear HẺM 14x10 m (phòng lớn, biến thể lightmap): **https://hem-3d.vercel.app**
- Bản render sẵn 287 khung (hướng phụ A): https://hollow-oak-lounge.vercel.app

Công thức nhìn thật rút từ https://www.finely-crafted.com, ghi ở `references/finely-recipe.md`. Bản làm theo kiểu đưa link cho AI tự đoán (https://hem-showroom.vercel.app, path tracing trong trình duyệt) bị giật và nhìn giả, lý do ghi ở `references/pitfalls.md`.

`SKILL` dưới đây là thư mục chứa file này. Scripts copy vào project rồi chạy từ thư mục project.

## Nguyên tắc

- **Mặc định làm hướng B (bake + WebGL), giống Finely.** Thành đã so 2 hướng và chốt B: nét ở mọi màn hình, chuyển động thật 60 khung/giây. Hướng A (render sẵn từng khung) chỉ làm khi user yêu cầu.
- **Duyệt trước, dựng sau.** 4 cổng: concept, món chính, 3 ảnh Cycles, bản web local. Chưa qua cổng thì không làm bước sau.
- **Ảnh Cycles chưa thật thì web không thể thật.** Sửa ánh sáng, vật liệu ở Blender. Đừng sửa ở code web.
- **Đường đi như khách bước vào tiệm:** đứng ngoài nhìn vào, qua cửa, dừng nhìn toàn cảnh, đi 1 vòng qua từng khu, quay đầu chậm, tới món chính thì chậm lại.
- **Không dùng lại asset của web mẫu** (JS, ảnh, model, font, logo). Tải về chỉ để phân tích, để ngoài project, không commit.
- **Thương hiệu hư cấu** trừ khi làm cho khách có thương hiệu thật. Không logo, nhãn, tên thật của hãng khác trong cảnh.
- **Đồ nội thất lấy đồ scan** (Poly Haven CC0). Chỉ dựng bằng code khối kiến trúc phẳng và vật xoay tròn đơn giản (ly, chai, chao đèn). Ghế, sofa dựng bằng code lộ CG ngay.
- **Ảnh concept tạo bằng Codex image gen** (`tools/concept.py`, gọi `codex exec` với tool `image_gen` của gói ChatGPT đang login). Không dùng API ảnh trả phí.
- **Model 3D AI là tuỳ chọn có tốn phí** (fal.ai Hunyuan, `tools/fal3d.py`). Báo giá cho user trước khi gọi. Key đọc từ biến môi trường hoặc `.env`, không bao giờ in ra.
- **Không cài package mới khi chưa hỏi.** Cần sẵn: Blender (đã chạy trên 5.2.1, tên input Principled BSDF cần bản 4.0 trở lên), Python có numpy + Pillow + playwright, ffmpeg, Node, Chrome, Vercel CLI.
- Ảnh chụp kiểm tra vào `screenshots/` trong project. Chụp xong tự mở ảnh ra xem rồi mới báo.

## Bước 0. Chốt brief (AskUserQuestion, 1 lượt)

1. Loại tiệm và thương hiệu (thật của khách hay hư cấu), cỡ phòng (dài x rộng x cao).
2. 1 đến 3 món chính (hero) cần nhìn rõ nhất, các khu trong tiệm (kệ, quầy, phòng thử...).
3. Web tham khảo nếu có (không bắt buộc).
4. Ngân sách: số giờ làm, số tiền model AI.
5. Màn hình người xem chủ yếu dùng (1440, 1920 hay lớn hơn), máy có card NVIDIA không, đã có Blender chưa.

Phòng trên khoảng 60 m2 hoặc tường, sàn có texture rõ thì dùng biến thể phòng lớn (Bước 8B).

## Bước 1. Phân tích web tham khảo bằng REA (tuỳ chọn)

Bỏ qua bước 1 và 2 khi user không gửi link: công thức Finely đã có sẵn trong `references/finely-recipe.md`. Có link thì làm để biết web đó nhìn thật nhờ đâu. Chi tiết lệnh: `references/rea.md`. Tóm tắt:

```bash
npx -y rea-agents@latest --version
# mở Chrome riêng: --remote-debugging-port=9222 --user-data-dir=<thư mục tạm> <link web mẫu>, bấm qua intro
npx -y rea-agents@latest list-browser-targets http://127.0.0.1:9222 --format json > re/<site>/evidence/01-targets.json
npx -y rea-agents@latest inspect-web-page http://127.0.0.1:9222 <targetId> --observation-ms 3000 --format json > re/<site>/evidence/02-inspect-page.json
npx -y rea-agents@latest analyze-web-bundle http://127.0.0.1:9222 <targetId> --observation-ms 2000 --format json > re/<site>/evidence/03-web-bundle.json
node $SKILL/scripts/re/shaders.js <bundle tải về>.js > re/<site>/evidence/04-shaders.txt
```

Tìm cho ra: engine gì, ánh sáng tính realtime hay bake sẵn (ảnh lightmap lớn, UV thứ 2), sàn phản chiếu thế nào, camera cao bao nhiêu, hậu kỳ gì, tải bao nhiêu MB.

## Bước 2. Báo cáo 3 ngăn (chỉ khi có bước 1)

Viết `re/<site>/bao-cao.md` theo khung trong `references/rea.md`: **quan sát được** (mỗi dòng có file làm bằng chứng), **suy luận**, **chưa rõ**, thêm bảng "vì sao bản cũ nhìn giả". Ví dụ đầy đủ: `references/finely-recipe.md`.

Gửi user phần kết luận (công thức xếp theo mức quan trọng). Hướng làm:
- **B. Bake + WebGL (mặc định).** Cách Finely. Nét đúng độ phân giải màn hình, chuyển động thật. Kính và đồ bóng kém Cycles một chút.
- **A. Render khung sẵn (chỉ khi user yêu cầu).** Ảnh từng khung đẹp nhất, nhưng giãn mờ trên màn lớn hơn cỡ render, và cuộn là chuyển dần giữa các ảnh nên kém mượt. Số đo: `references/pitfalls.md`.

## Bước 3. Plan, chi phí, concept (cổng 0)

Plan gửi user gồm: phạm vi (có gì, không có gì), bảng bước với giờ nhanh / dự kiến / chậm, cổng duyệt, chi phí từng món, thứ tự cắt khi trễ giờ. Số tham chiếu từ Hollow Oak:

| Việc | Số thật |
|---|---|
| Bản đầu (dựng, render 144 khung, web, deploy) | khoảng 5,7 giờ, plan dự kiến 8,4 |
| Render | trung vị 30 giây/khung ở 1600x900, RTX 4050 laptop. 143 khung chạy 77 phút |
| Chi phí model AI | khoảng 0,87 USD: 2 ảnh concept 0,27 (lúc đó dùng Gemini, giờ dùng Codex), giày 3D Hunyuan PBR 0,525, ảnh mẫu giày 2 lần x 0,04 |
| Dung lượng tải | desktop 20,5 MB, iPhone 4,3 MB (Finely 26,7 MB) |

Concept: 2 ảnh 16:9, 1 góc rộng từ lối vào, 1 cận món chính ở cuối đường đi.

```bash
python tools/concept.py concept-01-wide "photoreal interior photo, ..." -i refs/mau-01.png
python tools/concept.py concept-02-close "..."
```

Ghi rõ cho user bản thật sẽ khác concept ở đâu (đồ scan có hình dạng cố định, nắng Cycles tính theo vật lý). **Dừng chờ duyệt.**

## Bước 4. Tạo project

```bash
P=<thư mục project>; mkdir -p "$P"/{assets,frames,renders/look,renders/gate,renders/anim,renders/seedtest,refs,screenshots,web}
cp -r $SKILL/scripts/blender $SKILL/scripts/tools "$P"/
cp $SKILL/scripts/bake.cmd $SKILL/scripts/render.cmd $SKILL/scripts/xem-website.cmd "$P"/
cp -r $SKILL/template/web3d "$P"/web3d                   # hướng B (mặc định), phòng nhỏ: bake màu vào texture
# phòng lớn: cp -r $SKILL/template/web3d/vendor "$P"/web3d/ && cp $SKILL/template/web3d-lightmap/* $SKILL/template/web3d-lightmap/.vercelignore "$P"/web3d/ && cp $SKILL/scripts/bake_lightmap.cmd "$P"/
cp $SKILL/template/{index.html,vercel.json,.vercelignore,.gitignore,grain.png} "$P"/web/   # hướng A; web/frames.json cũng là nơi bake.py đọc hotspot
```

Ảnh chụp web mẫu để trong `refs/`, chỉ tham khảo, không deploy.

## Bước 5. Asset và món chính (cổng 1)

```bash
python tools/fetch_ph.py --tex=<id>,<id> --model=<id>:2k,<id>:1k --hdri=<id>:2k   # Poly Haven CC0, tối đa 3 luồng
blender -b -P blender/inspect_ph.py                                                # mỗi .blend có object gì, cỡ bao nhiêu
```

Món chính không có trên Poly Haven thì (tuỳ chọn, tốn phí):

```bash
python tools/fal3d.py hero "plain white leather low-top sneaker, no logos, no text" --image-only   # ~0,04 USD, duyệt ảnh trước
python tools/fal3d.py hero "" --from-url=<url trong assets/ai/hero.url> --pbr                      # Hunyuan 3D PBR ~0,525 USD
blender -b -P blender/clean_ai_model.py -- assets/ai/hero.glb 0.285 --shoe                          # dài thật 0,285 m
```

Chỉ tạo 1 chiếc, chiếc kia lật gương. Mở `renders/look/hero_studio.png` cho user. **Dừng chờ duyệt.**

## Bước 6. Dựng cảnh

Sửa `blender/build_scene.py` (đang là cảnh Hollow Oak, chạy được ngay sau `fetch_ph.py` + `make_label.py`). Giữ bố cục file, thay các phần ROOM / PROPS / LIGHT / CAMERA / HOTSPOTS.

- Đúng tỉ lệ mét, trần 3 đến 3,5 m. Mọi cạnh bevel 2 đến 5 mm.
- Tường, sàn, quầy: màu phẳng + roughness có noise (`noise_rough`, `pbr(grey=..., rough=(lo, hi))`). Sàn bóng loang.
- Kính: `common.glass()` (trong suốt với tia bóng đổ). Cửa sổ không lắp kính.
- Nắng: Sun lamp góc thấp màu ấm, HDRI trời clamp lại, area light portal ở cửa sổ. Đèn thả: point light nhỏ + chao có emission.

```bash
blender -b -P blender/build_scene.py      # -> scene.blend + web/frames.json. "BUILD missing images" phải là []
```

## Bước 7. Ánh sáng và đường camera (cổng 2)

Ảnh Cycles là trần chất lượng của bản web. Duyệt ánh sáng trên ảnh Cycles trước khi bake:

```bash
blender -b scene.blend -P blender/render_setup.py -o //renders/look/k### -f 0,<giữa>,<cuối> -- --look --exposure 1.6
python tools/contact_sheet.py renders/look/sheet.png 2 800 renders/look/k*.png refs/fc-*.png
```

Gửi user 3 ảnh đặt cạnh ảnh web mẫu. **Dừng chờ duyệt.** Ở hướng B, `N_FRAMES` chỉ là số mẫu của đường camera, 287 là đủ.

Đường camera như người bước vào tiệm: dừng ở cửa nhìn toàn cảnh, đi chậm, quay đầu chậm (pitch trong ±5 độ, mỗi lần quay không quá 60 độ giữa 2 điểm khoá), tới món chính thì chậm lại.

## Bước 8B. Bake ánh sáng (hướng B)

Sửa khối `EDIT` đầu `blender/bake.py`: biên phòng, object kiến trúc (`ARCH`, ghép thành 1 atlas 4096, sàn có atlas riêng), tiền tố đồ scan/AI (`PROPS`, bake qua UV riêng của chúng), tiền tố đồ vẽ trực tiếp (`LIVE`: kính, chai, đèn, lá cây có alpha).

```bash
blender -b scene.blend -P blender/bake.py -- --samples 64 --scale 0.25   # chạy thử khoảng 1 phút, kiểm lỗi
```

Rồi bấm đúp `bake.cmd` (256 mẫu, tường và sàn tự nhân 4). Hollow Oak: 15 phút trên RTX 4050 laptop. Ra `web3d/assets/`:
- `lounge.glb`: sàn, phòng, đồ scan, mang texture bake (màu x ánh sáng, chia 2, sRGB). Draco.
- `live.glb`: kính, chai, ly, đèn, cây.
- `env.hdr`: ảnh 360 trong phòng để phản chiếu.
- `walk.json`: camera từng khung, hotspot (vị trí 3D, bị che ở khung nào).
- Tự thêm `sky.hdr`: bản 1k của HDRI dùng trong cảnh, tải từ Poly Haven, để thấy trời qua cửa sổ.

### Phòng lớn: lightmap + texture lặp (`bake_lightmap.py`, `template/web3d-lightmap`)

Dùng khi phòng trên khoảng 60 m2 hoặc tường, sàn có texture rõ (bê tông, gạch). Bake màu vào 1 atlas 4096 cho phòng 14x10 m thì tường nhoè. Cách làm (HẺM, ví dụ dựng cảnh: `blender/build_shop_example.py`):
- **Kiến trúc** = texture lặp nét (UV0) x lightmap chỉ ánh sáng (UV1, bake DIFFUSE tắt color pass, lưu light/6). Web: `MeshBasicMaterial({ map, lightMap, lightMapIntensity: 6π })` (Basic nhân lightmap với 1/π). Sàn: shader riêng albedo x lightmap + phản chiếu.
- **Hàng hoá AI** (áo, giày, ma-nơ-canh) giữ texture gốc, ánh sáng bake theo đỉnh (attribute `LIGHT`, bake target VERTEX_COLORS). Web: `MeshBasicMaterial({ map, vertexColors })` + sàn sáng tối thiểu `?gf=0.4` để đỉnh bị khuất giữa các áo không thành vệt đen.
- **Đồ scan nhỏ** bake full màu qua UV riêng như phòng nhỏ.
- **Vẽ sống:** neon, LED, gương, cây.
- Đặt tên theo tiền tố, sửa danh sách `ATLAS` / `PROPS` / `GOODS` / `LIVE` đầu `bake_lightmap.py`. Bấm đúp `bake_lightmap.cmd`. HẺM: 20 phút RTX 4050, tải khoảng 21 MB.

## Bước 9B. Web realtime (cổng 3)

Sửa chữ trong `web3d/index.html` (chỗ `EDIT`). `web3d/main.js` thường không cần sửa:
- Phòng: `MeshBasicMaterial` hiện texture bake. Đồ scan: texture bake đi vào emission, shader bỏ phần diffuse sống, chỉ giữ phản chiếu (kim loại, độ bóng).
- Sàn: chụp phòng 1 lần lúc tải vào cube map 512 (`CubeCamera`), chiếu lên khối hộp của phòng (box projection), đọc mờ ở mip 3, trộn theo Fresnel. Rẻ hơn `Reflector` vẽ lại phòng mỗi khung. Gương: buồng thử có cube riêng đặt giữa buồng, gương trên tường dùng cube của phòng.
- Đồ nhỏ gộp theo vật liệu (khoảng 200 draw call còn 25).
- Cuộn: tốc độ chia theo lượng hình đổi trên màn (quay 1 radian tính bằng đi 2,5 m), lướt 0.9. Chuột quay đầu thật 2,2 độ.
- Khử răng cưa: vật mảnh và sáng (vạch LED, thanh treo, mép áo) không khử răng cưa thì nhấp nháy khi cuộn. `web3d-lightmap` bật MSAA mọi khung (`?noaa` để tắt), pixel ratio tối đa 1.5. Làm được vì mọi thứ là `MeshBasicMaterial`. `web3d` (phòng nhỏ, đồ có vật liệu PBR sống) không gánh nổi MSAA trên card Intel: đang cuộn không khử, dừng 0,1 giây vẽ 1 khung FXAA, `?aa` để thử MSAA.
- Tham số đo: `?aa` / `?noaa`, `?aniso=`, `?norefl`, `?nolive`, `?noglass`, `?pr=`, `?blur=`, `?gf=`, `?neon=`.

```bash
python tools/serve.py 8770
python tools/gpu3d.py http://127.0.0.1:8770/web3d/index.html          # Chrome vẽ bằng card nào (laptop 2 card thường là Intel)
python tools/perf3d.py "http://127.0.0.1:8770/web3d/index.html?a"     # p95 khoảng cách khung, số khung > 25 ms
python tools/shoot3d.py http://127.0.0.1:8770/web3d/index.html screenshots/t1 0 0.25 0.5 0.75 1
python tools/capture_scroll.py http://127.0.0.1:8770/web3d/index.html rt --vw=1920 --vh=1080
```

Đạt khi (đo ở cỡ màn của user, chạy 2 lần vì máy dao động): p95 khoảng 17 ms, khung > 25 ms dưới 5%, không lỗi console ngoài cảnh báo X4122/X3595 của ANGLE. **Dừng cho user kéo thử bản local.**

## Bước 10B. Deploy

```bash
cd web3d && vercel deploy --prod --yes --name <tên-project>
python ../tools/perf3d.py "https://<tên>.vercel.app/?live"
```

`.vercelignore` bỏ `assets/tex` (PNG bake gốc). Hollow Oak tải khoảng 13 MB.

---

# Hướng phụ A: render sẵn từng khung

Chỉ làm khi user yêu cầu. Các bước dưới thay cho 8B đến 10B.

## Bước 7A. Ánh sáng, đường camera, số khung (cổng 2 và 2b)

```bash
blender -b scene.blend -P blender/render_setup.py -o //renders/look/k### -f 0,<giữa>,<cuối> -- --look --exposure 1.6
blender -b scene.blend -P blender/render_setup.py -o //renders/gate/g### -f 0,<giữa>,<cuối> -- --exposure 1.6      # chất lượng thật, đo giây/khung
blender -b scene.blend -P blender/render_setup.py -o //renders/seedtest/s0_### -f <khung tối> -- --exposure 1.6 --seed 0
blender -b scene.blend -P blender/render_setup.py -o //renders/seedtest/s1_### -f <khung tối> -- --exposure 1.6 --seed 1
blender -b scene.blend -P blender/render_setup.py -o //renders/anim/a### -a -- --preview --exposure 1.6               # xem đường đi
python tools/contact_sheet.py renders/look/sheet.png 2 800 renders/gate/*.png refs/fc-*.png
```

- Camera: 4 đến 5 điểm khoá (`KEYS`), cao 1,5 m, ống 24 mm. Pitch trong khoảng ±5 độ, riêng cảnh cuối có thể cúi xuống món chính.
- Cỡ render (`RES`): bằng màn hình đích của user, rộng và cao đều là số chẵn (H.264 4:2:0 từ chối số lẻ). 1600x900 giãn 1,26 lần trên màn 1920 và mờ thấy rõ.
- Số khung (`N_FRAMES`): đủ để mỗi khung lệch khung kề khoảng 7 px trở xuống. Hollow Oak: 144 khung lệch 10 đến 19 px là giật, 287 khung còn khoảng 6,5 px.
- Seed test: chênh lệch giữa 2 seed là trần flicker. Hollow Oak đạt tối đa 3,34 mức xám ở khối 16 px.
- Gửi user 3 ảnh gate đặt cạnh ảnh web mẫu. **Dừng chờ duyệt (cổng 2).**
- Render 24 khung liền nhau ở đoạn tối nhất, ráp vào web (Bước 9), cho user tự kéo thử. **Dừng chờ duyệt (cổng 2b).**

## Bước 8A. Render cả loạt

User bấm đúp `render.cmd` (hoặc bật tách khỏi phiên Claude). Đặt `BLENDER` nếu blender không có trên PATH, `EXPOSURE` nếu khác 1.6. Ngắt giữa chừng thì chạy lại, khung xong được bỏ qua. Ước giờ = số khung x giây/khung đo ở gate. Cắm sạc, tắt sleep.

Trên macOS/Linux: `blender -b scene.blend -P blender/render_setup.py -a -- --exposure 1.6 >> renders/render.log 2>&1`.

Muốn dày khung sau khi đã render: đổi `N_FRAMES` từ n thành 2n-1, chạy lại build, chuyển `frames/f{k}` sang `f{2k}`, bump `VERSION`, chạy `render.cmd`. Chỉ khung lẻ được render.

## Bước 9A. Đóng gói và web (cổng 3)

```bash
python tools/flicker_scan.py                     # khung nhảy sáng (đọc kết quả theo pitfalls.md)
python tools/contact_sheet.py renders/contact.png 6 400 "frames/f*0.png"
python tools/pack_frames.py                      # WebP 960 + cỡ đủ, có bloom, chạy được khi đang render
python tools/pack_h264.py                        # H.264 all-intra cho desktop (WebCodecs), cần ffmpeg
```

Sửa chữ trong `web/index.html` (chỗ đánh dấu `EDIT`). Caption bám theo keyframe (`data-key`) hoặc theo tiến độ cuộn (`data-from`/`data-to`). Hotspot lấy từ `frames.json`, đã tự ẩn khi ra mép hoặc bị che.

```bash
python tools/serve.py 8770                                   # hoặc bấm đúp xem-website.cmd
python tools/shoot_site.py http://127.0.0.1:8770/web/index.html local
python tools/scroll_feel.py http://127.0.0.1:8770/web/index.html
python tools/capture_scroll.py http://127.0.0.1:8770/web/index.html local --vw=1920 --vh=1080
```

Đạt khi: p95 khoảng cách khung khi cuộn khoảng 17 ms, 0 lần trên 50 ms, không lỗi console, hotspot nằm đúng món đồ, iPhone chạy được. Đo ở cỡ màn hình thật của user. **Dừng cho user kéo thử bản local.**

## Bước 10A. Deploy Vercel

```bash
cd web && vercel deploy --prod --yes --name <tên-project>
curl -sI https://<tên>.vercel.app/frames-webp/<v>/960/f000.webp | grep -i cache-control   # immutable
```

`.vercelignore` bỏ file `.py`, `.cmd`. Mỗi lần render lại phải bump `VERSION` trong `build_scene.py` để đổi thư mục `frames-*/<v>/`, cache cũ không trả khung cũ. Chụp lại bằng `shoot_site.py` trên link thật.

## Tham khảo

- `references/rea.md`: lệnh REA, khung báo cáo 3 ngăn.
- `references/finely-recipe.md`: công thức Finely, so sánh hướng A và B.
- `references/pitfalls.md`: bẫy đã gặp, số đo, giới hạn còn lại (cả hướng A và B). Đọc trước khi debug giật, mờ, nhảy sáng, tụt khung.
