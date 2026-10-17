# Công thức showroom nhìn thật

Rút ra khi làm Hollow Oak Lounge và HẺM (10/2026). Style tham khảo: finely-crafted.com.

## Kết luận

Ánh sáng không tính trên trình duyệt. Cycles tính trước (bake) trên máy mạnh, lưu vào ảnh. Trình duyệt chỉ đọc ảnh đó ra và vẽ lại phòng mỗi khung. Nắng xuyên cửa, bóng mềm dưới ghế, ánh sáng dội tường đều tính sẵn.

Xếp theo mức quan trọng:

1. Ánh sáng bake sẵn, có ánh sáng dội (GI) và vệt nắng.
2. Sàn phản chiếu mờ, độ bóng loang không đều.
3. Camera ở tầm mắt người: 1,5 đến 1,6 m, ống 24 mm.
4. Hậu kỳ nhẹ: tone map 1 lần ở cuối (AgX), bloom chỉ ở đèn, vignette, grain.
5. Tường, sàn, nội thất phần lớn là màu phẳng hoặc texture lặp. Texture chi tiết dành cho vài món chính.
6. Khử răng cưa ở mọi khung khi có vật mảnh và sáng (vạch LED, thanh treo).

Phòng đẹp nhờ ánh sáng. Texture xếp sau.

## Vì sao bản tự làm thường nhìn giả

| Triệu chứng | Nguyên nhân | Cách sửa |
|---|---|---|
| Góc tường sáng đều, đồ như dán lên nền | Không có GI, không có AO | Bake bằng Cycles |
| Bóng cứng hoặc không có bóng dưới ghế | Shadow map realtime | Bake, bóng mềm theo kích thước nguồn sáng |
| Sàn lì, không phản chiếu | Thiếu reflection | Phản chiếu mờ (cube map chụp phòng + box projection) |
| Bề mặt nào cũng bóng như nhựa | Roughness đồng đều | Roughness loang có noise |
| Màu bệch hoặc cháy | Sai color space, tone map 2 lần | Tone map đúng 1 lần ở cuối |
| Cảm giác drone bay | Camera cao, FOV rộng | Camera 1,5 m |
| Đồ tròn như đồ chơi | Nội thất dựng bằng code | Đồ scan Poly Haven, model AI cho món chính |
| Ánh sáng nhảy khi cuộn | Path trace trong trình duyệt, ít mẫu mỗi khung | Bake sẵn, trình duyệt không tính ánh sáng |
| Cạnh nhấp nháy khi cuộn | Không khử răng cưa lúc đang di chuyển | MSAA mọi khung |
| Kéo bị giật | Tua video theo cuộn | Vẽ realtime 60 khung/giây |

## 2 hướng làm

| | B. Bake + WebGL (mặc định) | A. Render khung sẵn (chỉ khi user yêu cầu) |
|---|---|---|
| Ánh sáng | Cycles bake vào texture, trình duyệt vẽ realtime | Cycles path trace từng khung |
| Chất lượng hình | Kính, sàn bóng giả lập, kém Cycles một chút | Bằng ảnh Cycles |
| Độ nét | Nét ở mọi màn hình | Cố định theo cỡ render, màn rộng hơn thì giãn mờ |
| Chuyển động | 60 khung/giây thật | Chuyển dần giữa các ảnh, kém mượt |
| Ví dụ | hollow-oak-lounge-3d.vercel.app, hem-3d.vercel.app | hollow-oak-lounge.vercel.app |

## Áp vào 2 ví dụ

Hollow Oak (phòng nhỏ 7x6 m):
1. Nắng chiều Sun lamp thấp 17 độ, HDRI trời qua cửa sổ, 3 đèn thả. Bake màu x ánh sáng vào texture.
2. Sàn bê tông Poly Haven, roughness 0.10 đến 0.34.
3. Đồ scan cho thùng gỗ, ghế, chai vang, cây. Giày AI là món chính.

HẺM (phòng lớn 14x10 m):
1. Nắng xiên qua mặt tiền, đèn ray, LED kệ giày, neon. Kiến trúc = texture lặp x lightmap chỉ ánh sáng; quần áo AI = texture gốc x ánh sáng theo đỉnh.
2. Sàn bê tông xám bóng, phản chiếu từ cube map chụp phòng 1 lần lúc tải.
3. Đường đi 13 điểm: hẻm, cửa, toàn cảnh, kệ hoodie, góc skate, mural, tường giày, phòng thử, hàng mới, quầy, bàn giữa.
