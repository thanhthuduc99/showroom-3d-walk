# Bẫy đã gặp (Hollow Oak, 14-15/10/2026)

Máy đo: laptop RTX 4050 6 GB, Blender 5.2.1, Chrome trên Windows 11. Số liệu lấy từ log và lần đo thật.

## Dựng cảnh Blender

- **Model nhập từ glTF ở chế độ xoay quaternion.** Gán `rotation_euler` không có tác dụng. Đôi giày AI bị quay gót về camera, chỉ phát hiện sau khi deploy, mất 73 phút render lại. Đã sửa: `common.dup()` đặt `rotation_mode = 'XYZ'`. Bài học: render 1 ảnh khung cuối ở chất lượng thật, xem món chính đúng hướng chưa, rồi mới render cả loạt.
- **Texture Poly Haven không đúng màu như tên.** `black_walnut_veneer_01` thật ra màu sáng, `smooth_concrete_floor` màu nâu. Dùng `pbr(..., tint=...)` hoặc `pbr(..., grey=...)` để ép lại màu.
- **HDRI có mặt trời riêng.** `lonely_road_afternoon_puresky` có mặt trời 9 độ chiếm 55% năng lượng, làm loạn vệt nắng. Clamp HDRI (node Vector Math MINIMUM 25) rồi dùng Sun lamp riêng để điều khiển hướng nắng.
- **Kính cửa sổ chặn nắng** khi tắt caustics. Không lắp kính, chỉ để khung đen. Có thêm area light làm portal ở cửa sổ.
- **Kính đổ bóng đen.** Material kính trộn Transparent BSDF theo `Is Shadow Ray` (`common.glass()`), ly và chai mới cho ánh sáng đi qua.
- **Asset Poly Haven kèm vật thừa.** `potted_plant_02` có object `_dirt` là vệt đất rơi trên sàn. Lọc bỏ khi append. Chạy `blender -b -P blender/inspect_ph.py` để xem mỗi file `.blend` chứa gì, kích thước bao nhiêu.
- **Texture tím (mất file).** Lưu `.blend` trước khi append để đường dẫn tương đối đúng. Build in `BUILD missing images` phải rỗng.
- **Model AI bóng như nhựa.** Bỏ map metallic/roughness của AI, đặt metallic 0, roughness 0.5, nhân albedo 0.86 cho đồ trắng khỏi cháy dưới nắng (`clean_ai_model.py`).
- **Ghế, sofa dựng bằng code lộ CG ngay.** Chỉ dựng bằng code những khối kiến trúc phẳng (tường, quầy, kệ, nan trần) và vật xoay tròn đơn giản (ly, chai, chao đèn). Đồ nội thất lấy đồ scan.

## Ánh sáng và render

- **Exposure:** 3 ảnh duyệt ở exposure 1.3 còn tối. So cạnh nhau 1.3 và 1.6 trên khung 0, chốt 1.6.
- **Seed test trước khi render cả loạt:** render cùng 1 khung tối với seed 0 và seed 1, đo chênh lệch. Hollow Oak: trung bình 0,92 mức xám, khối 16 px p99 1,84, tối đa 3,34 trên 255. Đây là trần flicker. Cao hơn thì tăng `adaptive_min_samples` lên 128, threshold 0.007.
- **Seed cố định, tắt animated seed.** Mỗi khung khử noise riêng nên seed đổi theo khung làm mảng sáng mờ đổi hình liên tục (lỗi của bản HẺM: path tracer trong trình duyệt 24 mẫu/px).
- **Thông số đã chạy ổn:** 512 samples, adaptive 0.01, min 64, OIDN có albedo + normal, prefilter ACCURATE, caustics tắt, clamp indirect 8, filter glossy 1.0, persistent data, AgX "Medium High Contrast".
- **Thời gian render:** 1600x900 trên RTX 4050 laptop, trung vị 30 giây/khung (25 đến 73 giây). 143 khung chạy 77 phút.
- **Render phải chạy được tiếp khi bị ngắt.** Dùng animation render của Blender với `use_overwrite=False` + `use_placeholder=True`, chạy qua `render.cmd`. File 0 byte là khung dở, `render.cmd` xoá trước khi chạy lại. Không viết vòng lặp Python render từng khung.
- **Đừng chạy render như task nền của phiên Claude.** Phiên restart là render chết. User bấm đúp `render.cmd`, hoặc bật tách khỏi phiên (Windows: `Start-Process render.cmd`). Cắm sạc, tắt sleep.
- **Kết quả flicker sau render:** sai phân bậc 2 của độ sáng toàn khung tối đa 0,078 mức xám (144 khung), 0,043 (287 khung). Khung chen giữa so với trung bình 2 khung bên cạnh: 0,036.
- **Đọc `flicker_scan.py` cho đúng.** Nó liệt kê cả 1 dải khung liền nhau ở đoạn quay người nhanh (f098 đến f12x ở bản 144, f195 trở đi ở bản 287). Đó là chuyển động, không phải nhảy sáng. Flicker thật hiện ra thành khung lẻ loi. Gặp dải liền thì kiểm lại bằng độ sáng toàn khung như trên.

## Khung hình và đường đi

- **144 khung là thưa.** Mỗi khung lệch khung kề 10 đến 19 px, đoạn quay người nhìn xuống thùng gỗ khoảng 17 px. User thấy giật. Render thêm nên tăng số khung, không tăng samples: ảnh đã đủ sạch.
- **Làm dày khung không phải render lại.** Đổi `N_FRAMES` từ n thành 2n-1 thì khung chẵn của bản mới trùng khít camera bản cũ (đã kiểm tra: sai lệch ma trận 0). Copy khung cũ `f{k}` sang `f{2k}`, bump `VERSION`, chạy lại `render.cmd`, Blender chỉ render khung lẻ. 287 khung: mỗi bước còn khoảng 6,5 px.
- **Tăng tần số quét màn hình không hết giật.** 60 Hz hay 120 Hz vẫn chỉ có ngần ấy ảnh khác nhau.
- **Nội suy hướng nhìn theo yaw/pitch**, không nội suy điểm nhìn, nếu không quay đầu quá 90 độ là camera cúi xuống sàn (`walk.py`).

## Player trên web

Từng bước Hollow Oak đã đi qua, để không lặp lại:

| Cách | Kết quả đo |
|---|---|
| Tua 1 file MP4 theo cuộn (bản HẺM) | Giật: mỗi lần kéo phải seek, giải mã lại từ keyframe gần nhất |
| 144 ảnh WebP 1600 trong bộ nhớ, trộn 2 khung kề | 1 đến 10 lần khựng trên 50 ms, p95 33 ms/khung |
| 287 ảnh WebP 1600 | Tệ hơn: 6 đến 43 lần khựng. 287 ảnh 1600 vượt ngân sách giải mã ảnh của Chrome, card Intel không kịp |
| WebP 960 lúc cuộn, tải bản 1600 khi dừng | Mượt (p95 17 ms, 0 khựng) nhưng mờ khoảng nửa giây sau khi dừng. User chê |
| **WebCodecs: mỗi khung 1 chunk H.264 all-intra (bản cuối, desktop)** | Nét 1600 cả lúc cuộn, p95 17 ms, 0 khựng. Độ nét lúc cuộn 148 so với 62 đến 79 của bản WebP |

Chi tiết bản cuối:
- `pack_h264.py`: CRF 18, `keyint=1`, `repeat-headers=1`, `aud=1`, gắn tag BT.709 để màu giải mã ra đúng (lệch khoảng 2 trên 255 mức so với WebP). Khoảng 71 KB/khung.
- Trình duyệt chỉ giữ khoảng 7 `VideoFrame` quanh vị trí xem, đóng frame cũ ngay.
- Điện thoại và trình duyệt không có `VideoDecoder`: dùng WebP, 960 lúc cuộn, bản đủ nét khi dừng, phát 1 khung trên 2. 287 ảnh nét giải mã sẵn chiếm khoảng 1,6 GB RAM, iPhone không chịu nổi.
- Dung lượng tải: desktop 20,5 MB (Finely 26,7 MB), iPhone 4,3 MB. Chỉ cần 24 khung đầu là mở được, phần còn lại tải ngầm theo thứ tự thô đến mịn (cứ 16 khung lấy 1 trước).
- Canvas 2D phải để `imageSmoothingQuality = 'low'`. Để 'high' thì Chrome dựng mipmap cho mỗi khung mới, card tích hợp giật.
- Cuộn: lướt theo thời gian, hệ số 0.9 mỗi 16,7 ms (khoảng 0,35 giây mỗi nấc chuột) để các nấc liền nhau nối thành 1 chuyển động. Độ giật theo nấc (CV) từ 0,53 xuống 0,29, bản WebCodecs 0,23.
- Canvas cao `100lvh` để thanh địa chỉ điện thoại ẩn hiện không làm cấp phát lại canvas giữa lúc cuộn.

## Giới hạn còn lại (đo 15/10, chưa sửa)

- **Mờ trên màn 1920.** Khung 1600x900 cộng 5% phóng to của hiệu ứng nghiêng chuột, giãn 1,26 lần trên màn 1920x1080. Độ nét lúc đứng yên: cửa sổ 1920 còn 77, cửa sổ 1440 là 115. Test ở cửa sổ 1440 sẽ không thấy lỗi này. Muốn nét: render đúng cỡ màn hình đích (`RES` trong `build_scene.py`), bỏ phóng to (`ZOOM = 1` trong `index.html`).
- **Tốc độ đi không đều.** Đoạn đi thẳng hình đổi ít, đoạn quay người mỗi nấc chuột làm hình đổi gấp 2 đến 4 lần. Khung nhảy mạnh lúc cuộn: Hollow Oak 18%, Finely 4%. Hướng sửa: tăng `TURN_COST` trong `walk.py` hoặc chia lại đường đi theo lượng hình chuyển động trên màn hình, rồi render lại.
- **Không mượt được như Finely** vì vẫn là chuyển dần giữa các ảnh. Muốn chuyển động thật và nét ở mọi màn hình thì làm hướng B trong `finely-recipe.md` (bake + WebGL).

## Đo

- `shoot_site.py`: chụp desktop 1440x900 + iPhone 390x844 ở 4 mốc cuộn + 1 hotspot mở, đo khoảng cách khung khi cuộn (p95, số lần trên 50 ms), thời gian `drawImage`, dung lượng tải, lỗi console.
- `scroll_feel.py`: độ đều khi cuộn bằng chuột có nấc (CV càng thấp càng mượt).
- `capture_scroll.py`: ghi từng khung màn hình thật sự hiện ra lúc cuộn (CDP screencast), đo bước dịch, khung lặp, khung nhảy, độ nét lúc cuộn so với lúc đứng yên. Chạy được cả trên web mẫu (`--setup=finely`) để so.
- Màn 60 Hz chỉ chụp được 1 khung mỗi 16,7 ms, không dày hơn được.
- Playwright trên Windows phải thêm `--disable-features=CalculateNativeWinOcclusion` (đã có trong script). Thiếu cờ này, cửa sổ đặt ngoài màn hình bị Chrome bóp còn 1 khung/giây và số đo sai.
- Đo ở đúng cỡ màn hình của user, không chỉ 1440.
