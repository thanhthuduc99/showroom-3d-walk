# Công thức Finely Crafted (rút gọn)

Nguồn: mổ https://www.finely-crafted.com/ (Monks, Awwwards Site of the Day 07/05/2021) bằng REA 6.4.0, ngày 14/10/2026. Đây là ví dụ đầy đủ của báo cáo 3 ngăn.

## Kết luận

Finely không tính ánh sáng trên trình duyệt. Họ dựng studio trong Unity, path trace ánh sáng trước bằng Bakery, lưu vào ảnh lightmap 4096x4096. Trình duyệt chỉ đọc ảnh đó ra. Nắng xuyên cửa, bóng mềm dưới ghế, ánh sáng dội tường đều tính sẵn.

Công thức, xếp theo mức quan trọng:

1. Ánh sáng bake sẵn, có ánh sáng dội (GI) và vệt nắng.
2. Sàn phản chiếu mờ, độ bóng loang không đều.
3. Camera ở tầm mắt người: 1,5 m.
4. Hậu kỳ nhẹ: tone map filmic, bloom chỉ ở đèn, vignette, grain.
5. Tường, sàn, nội thất phần lớn là màu phẳng. Texture chi tiết chỉ dành cho vài món chính (giày, chai, két sắt).

Phòng đẹp nhờ ánh sáng. Texture xếp sau.

## Quan sát được (có file làm bằng chứng)

| Phát hiện | Bằng chứng |
|---|---|
| Vue.js + GSAP + engine WebGL tự viết, `vendors.js` có OGL. Attribute kiểu Unity: `aPos`, `aUV0`, `aUV1`, uniform `_ViewProjection` | `03-web-bundle.json`, `04-shaders-app.txt` |
| Cảnh export từ Unity: `2.js` là JSON 370 transform, 73 material shader "Standard", 251 object. `3.js` thêm 176 object static | `2.js`, `3.js`, đọc bằng `scene.js` |
| Đèn tên `Bakery Directional Light`, `Bakery Spot Light`, `Bakery_Point Light_Left/Right` | `2.js` |
| 2 lightmap 4096x4096: `lights_on.jpg` 4,4 MB, `lights_projection.jpg` 3,2 MB. Mobile dùng bản 2048 | `02-inspect-page.json`, `app.js` |
| Shader phòng: albedo, roughness, metallic lưu theo đỉnh. Lightmap đọc bằng UV thứ 2 (`aUV1`). Màu cuối = (albedo + highlight mặt trời giả) x lightmap, rồi tone map filmic | shader #26, #27 |
| Sàn: render cảnh lật ngược vào render target (rộng/2, cao/4, có mipmap), đọc lại mờ theo roughness lấy từ `floor.webp`, trộn theo Fresnel | shader #19, `reflectionManager` |
| Đồ chính: PBR đủ map (Albedo, Normal, AO, MetallicSmoothness), chiếu bằng IBL (cubemap + BRDF LUT) | shader #13 |
| Bloom: threshold 1, strength 0.75, kênh alpha làm mask phát sáng | `app.js` |
| Camera y = 1,5 m suốt đường đi, intro 18 giây, điểm camera riêng cho từng hotspot, nghiêng nhẹ theo chuột, cuộn chuột để đi | `2.js`, `app.js` |
| Tải lần đầu khoảng 26,7 MB: ảnh 10,9 MB, JS 15,7 MB (phần lớn là mesh dạng JSON) | `02-inspect-page.json` |
| Canvas WebGL2 vẽ đúng bằng số điểm ảnh của cửa sổ (1440x813 ở cửa sổ 1440), nên nét ở mọi màn hình | `inspect-page` lần 2, 15/10 |

## Suy luận

- Texture đồ chính đặt tên theo preset "Unity Standard (Metallic)" của Substance Painter, khả năng cao texture bằng Substance.
- Bake bằng Bakery: suy từ tên đèn, bản ship không có file cấu hình bake.

## Chưa rõ

- Thông số bake (samples, số lần dội sáng).
- Engine có hàm jitter Halton (TAA), chưa xác nhận lúc chạy có bật hay không.
- `lights_projection` là trạng thái nào. Mới đọc từ shader, chưa quan sát lúc chạy.

## Vì sao bản tự làm thường nhìn giả

| Triệu chứng | Nguyên nhân | Finely xử lý |
|---|---|---|
| Góc tường sáng đều, đồ như dán lên nền | Không có GI, không có AO | Bake |
| Bóng cứng hoặc không có bóng dưới ghế | Shadow map realtime | Bake, bóng mềm theo kích thước nguồn sáng |
| Sàn lì, không phản chiếu | Thiếu reflection | Planar reflection mờ |
| Bề mặt nào cũng bóng như nhựa | Roughness đồng đều | Roughness loang, IBL lấy từ chính cảnh |
| Màu bệch hoặc cháy | Sai color space, tone map 2 lần | Tone map đúng 1 lần ở cuối |
| Cảm giác drone bay | Camera cao, FOV rộng | Camera 1,5 m |
| Đồ tròn như đồ chơi | Nội thất dựng bằng code | Model thật, có texture |
| Răng cưa, dải màu loang | Không AA, không grain | AA + grain nhẹ |

## Hollow Oak làm lại thế nào

Hai cách mang công thức này về đồ miễn phí:

| | A. Render khung sẵn (Hollow Oak dùng) | B. Bake lightmap + WebGL (Finely dùng) |
|---|---|---|
| Ánh sáng | Cycles path trace từng khung, 512 samples | Cycles bake vào lightmap, trình duyệt vẽ realtime |
| Chất lượng hình | Bằng ảnh Cycles, kính và sàn bóng thật nhất | Kính, sàn bóng phải giả lập, kém Cycles một chút |
| Độ nét | Cố định theo cỡ render, màn rộng hơn thì giãn | Nét ở mọi màn hình |
| Chuyển động | Tua khung theo cuộn, chỉ đi theo 1 đường | 60 khung/giây thật, xoay tự do được |
| Thời gian | Bản đầu khoảng 5,7 giờ làm + render máy chạy | Ước 8 đến 12 giờ làm + bake, chưa làm thử |

Hollow Oak chọn A vì lần thử bake trước (`phan-tailor`) bị chê giả: đồ nội thất dựng bằng code, lightmap chỉ 159 px/m nên ánh sáng nhoè, cả phòng chỉ có đèn spot, không có nắng. Với A, ảnh Cycles đã đạt thì web đạt. Giới hạn của A ghi ở `pitfalls.md`, mục Giới hạn còn lại.

Mapping 5 điểm công thức sang Hollow Oak:

1. Ánh sáng: Cycles render sẵn, nắng chiều Sun lamp thấp 17 độ, HDRI trời qua cửa sổ, 3 đèn thả.
2. Sàn: texture bê tông Poly Haven, roughness ép về 0.10 đến 0.34 cho bóng loang.
3. Camera: 1,5 m, ống 24 mm.
4. Hậu kỳ: AgX "Medium High Contrast" trong Blender, bloom cố định khi đóng gói (`pack_frames.bloom`), vignette + grain bằng CSS.
5. Màu phẳng: tường, quầy, kệ là khối đơn giản. Đồ scan Poly Haven cho thùng gỗ, ghế, chai vang, cây. Giày AI là món chính duy nhất.

## Bản quyền

JS, ảnh, model của Finely tải về chỉ để phân tích. Không dùng lại. DISCLAIMER của REA cũng ghi rõ không hỗ trợ copy code hay asset độc quyền.
