---
name: reverse-3d-room
description: Mổ một web 3D đẹp (kiểu finely-crafted.com) bằng REA để rút ra vì sao nó nhìn thật, rồi dựng lại 1 phòng 3D chân thật bằng đồ miễn phí - Blender Cycles render sẵn từng khung theo đường camera, web cuộn là đi bộ trong phòng, hotspot bấm xem món đồ, deploy Vercel. Có báo cáo 3 ngăn (quan sát / suy luận / chưa rõ), duyệt concept trước khi dựng, script Blender dựng cảnh + đường camera, đóng gói khung WebP + H.264 (WebCodecs), script đo giật và nhảy sáng. Dùng khi user nói "reverse web 3D", "REA reverse", "mổ web 3D này", "làm web 3D giống finely crafted", "phòng 3D nhìn thật", "web 3D nhìn giả quá", "website cuộn là đi bộ trong phòng", hoặc gửi link 1 web 3D muốn làm bản riêng nhìn thật như vậy.
---

# Reverse 3D Room

Ví dụ đã làm: Hollow Oak Lounge, https://hollow-oak-lounge.vercel.app (287 khung Cycles 1600x900, 3 hotspot). Làm lại theo công thức rút từ https://www.finely-crafted.com. Bản làm trước đó theo kiểu đưa link cho AI tự đoán (https://hem-showroom.vercel.app) bị giật và nhìn giả, lý do ghi ở `references/pitfalls.md`.

`SKILL` dưới đây là thư mục chứa file này. Scripts copy vào project rồi chạy từ thư mục project.

## Nguyên tắc

- **Duyệt trước, dựng sau.** 4 cổng: concept, món chính, 3 ảnh render thật, kéo thử 24 khung. Chưa qua cổng thì không làm bước sau.
- **Ảnh Cycles chưa thật thì web không thể thật.** Sửa ánh sáng, vật liệu ở Blender. Đừng sửa ở code web.
- **Không dùng lại asset của web mẫu** (JS, ảnh, model, font, logo). Tải về chỉ để phân tích, để ngoài project, không commit.
- **Thương hiệu hư cấu.** Không logo, nhãn, tên thật của hãng nào trong cảnh.
- **Đồ nội thất lấy đồ scan** (Poly Haven CC0). Chỉ dựng bằng code khối kiến trúc phẳng và vật xoay tròn đơn giản (ly, chai, chao đèn). Ghế, sofa dựng bằng code lộ CG ngay.
- **Ảnh concept tạo bằng Codex image gen** (`tools/concept.py`, gọi `codex exec` với tool `image_gen` của gói ChatGPT đang login). Không dùng API ảnh trả phí.
- **Model 3D AI là tuỳ chọn có tốn phí** (fal.ai Hunyuan, `tools/fal3d.py`). Báo giá cho user trước khi gọi. Key đọc từ biến môi trường hoặc `.env`, không bao giờ in ra.
- **Không cài package mới khi chưa hỏi.** Cần sẵn: Blender (đã chạy trên 5.2.1, tên input Principled BSDF cần bản 4.0 trở lên), Python có numpy + Pillow + playwright, ffmpeg, Node, Chrome, Vercel CLI.
- Ảnh chụp kiểm tra vào `screenshots/` trong project. Chụp xong tự mở ảnh ra xem rồi mới báo.

## Bước 0. Chốt brief (AskUserQuestion, 1 lượt)

1. Link web mẫu.
2. Không gian và 1 đến 3 món chính (hero) cần nhìn rõ nhất.
3. Ngân sách: số giờ làm, số tiền model AI.
4. Màn hình người xem chủ yếu dùng (1440, 1920 hay lớn hơn). Quyết định cỡ render, xem Bước 7.
5. Máy có card NVIDIA không, đã có Blender chưa.

## Bước 1. Mổ web mẫu bằng REA

Chi tiết lệnh: `references/rea.md`. Tóm tắt:

```bash
npx -y rea-agents@latest --version
# mở Chrome riêng: --remote-debugging-port=9222 --user-data-dir=<thư mục tạm> <link web mẫu>, bấm qua intro
npx -y rea-agents@latest list-browser-targets http://127.0.0.1:9222 --format json > re/<site>/evidence/01-targets.json
npx -y rea-agents@latest inspect-web-page http://127.0.0.1:9222 <targetId> --observation-ms 3000 --format json > re/<site>/evidence/02-inspect-page.json
npx -y rea-agents@latest analyze-web-bundle http://127.0.0.1:9222 <targetId> --observation-ms 2000 --format json > re/<site>/evidence/03-web-bundle.json
node $SKILL/scripts/re/shaders.js <bundle tải về>.js > re/<site>/evidence/04-shaders.txt
```

Tìm cho ra: engine gì, ánh sáng tính realtime hay bake sẵn (ảnh lightmap lớn, UV thứ 2), sàn phản chiếu thế nào, camera cao bao nhiêu, hậu kỳ gì, tải bao nhiêu MB.

## Bước 2. Báo cáo 3 ngăn

Viết `re/<site>/bao-cao.md` theo khung trong `references/rea.md`: **quan sát được** (mỗi dòng có file làm bằng chứng), **suy luận**, **chưa rõ**, thêm bảng "vì sao bản cũ nhìn giả". Ví dụ đầy đủ: `references/finely-recipe.md`.

Gửi user phần kết luận (công thức xếp theo mức quan trọng) và chọn hướng:
- **A. Render khung sẵn** (skill này): đẹp nhất, nhanh nhất. Chỉ đi theo 1 đường, nét cố định theo cỡ render.
- **B. Bake lightmap + WebGL** (cách Finely): nét mọi màn hình, xoay tự do. Lâu hơn, kính và sàn bóng kém Cycles. Skill này chưa có script cho B.

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
cp $SKILL/scripts/render.cmd $SKILL/scripts/xem-website.cmd "$P"/
cp $SKILL/template/{index.html,vercel.json,.vercelignore,.gitignore,grain.png} "$P"/web/
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

## Bước 7. Ánh sáng, đường camera, số khung (cổng 2 và 2b)

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

## Bước 8. Render cả loạt

User bấm đúp `render.cmd` (hoặc bật tách khỏi phiên Claude). Đặt `BLENDER` nếu blender không có trên PATH, `EXPOSURE` nếu khác 1.6. Ngắt giữa chừng thì chạy lại, khung xong được bỏ qua. Ước giờ = số khung x giây/khung đo ở gate. Cắm sạc, tắt sleep.

Trên macOS/Linux: `blender -b scene.blend -P blender/render_setup.py -a -- --exposure 1.6 >> renders/render.log 2>&1`.

Muốn dày khung sau khi đã render: đổi `N_FRAMES` từ n thành 2n-1, chạy lại build, chuyển `frames/f{k}` sang `f{2k}`, bump `VERSION`, chạy `render.cmd`. Chỉ khung lẻ được render.

## Bước 9. Đóng gói và web (cổng 3)

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

## Bước 10. Deploy Vercel

```bash
cd web && vercel deploy --prod --yes --name <tên-project>
curl -sI https://<tên>.vercel.app/frames-webp/<v>/960/f000.webp | grep -i cache-control   # immutable
```

`.vercelignore` bỏ file `.py`, `.cmd`. Mỗi lần render lại phải bump `VERSION` trong `build_scene.py` để đổi thư mục `frames-*/<v>/`, cache cũ không trả khung cũ. Chụp lại bằng `shoot_site.py` trên link thật.

## Tham khảo

- `references/rea.md`: lệnh REA, khung báo cáo 3 ngăn.
- `references/finely-recipe.md`: công thức Finely, so sánh hướng A và B.
- `references/pitfalls.md`: bẫy đã gặp, số đo, giới hạn còn lại. Đọc trước khi debug giật, mờ, nhảy sáng.
