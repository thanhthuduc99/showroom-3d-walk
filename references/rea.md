# Mổ web mẫu bằng REA

REA (Reverse Engineer Anything): https://github.com/morluto/rea, package npm `rea-agents`. Nó là CLI + MCP server, không phải plugin Claude Code. Chạy thẳng bằng `npx`, không cần cài global.

## Cài

- Node 22.18 trở lên (hoặc 24.11+). Node 22.14 vẫn chạy được, chỉ in cảnh báo `EBADENGINE`.
- Kiểm tra: `npx -y rea-agents@latest --version` (bản đã dùng: 6.4.0).
- Muốn dùng làm MCP thường xuyên thì phải đăng ký MCP rồi restart Claude Code. Việc này đổi cấu hình máy, hỏi user trước.

## Mở web mẫu trong Chrome riêng

Chrome có cổng debug, profile riêng (không dùng profile thật của user):

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=<thư mục tạm> --no-first-run --window-size=1440,900 https://<web-mẫu>/
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir=<thư mục tạm> https://<web-mẫu>/
```

Bấm qua cookie, nút Enter, bỏ video intro bằng tay cho tới khi cảnh 3D hiện ra. REA chỉ quan sát trang đang mở.

## 3 lệnh chính

```bash
mkdir -p re/<site>/evidence
npx -y rea-agents@latest list-browser-targets http://127.0.0.1:9222 --format json > re/<site>/evidence/01-targets.json
# lấy target_id của tab web mẫu trong file trên
npx -y rea-agents@latest inspect-web-page http://127.0.0.1:9222 <targetId> --observation-ms 3000 --format json > re/<site>/evidence/02-inspect-page.json
npx -y rea-agents@latest analyze-web-bundle http://127.0.0.1:9222 <targetId> --observation-ms 2000 --format json > re/<site>/evidence/03-web-bundle.json
```

- `inspect-web-page`: DOM, script, resource (kèm dung lượng), network, console, worker. Dùng để biết trang tải gì, nặng bao nhiêu, ảnh nào là lightmap.
- `analyze-web-bundle`: phân tích tĩnh các script, ra thư viện (three, OGL, GSAP, Vue...), tên attribute shader.
- Mỗi kết quả có `evidence_id`. Ghi id này vào báo cáo cạnh từng phát hiện.

Đọc nhanh bằng node, ví dụ in danh sách resource:

```bash
node -e 'const n=JSON.parse(require("fs").readFileSync("re/<site>/evidence/02-inspect-page.json","utf8")).normalized_result; for (const r of (n.resources.items||n.resources)) console.log(r.type||r.resource_type, r.url, r.size||"")'
```

## Đào sâu bằng 2 script tự viết

REA đưa ra danh sách file. Phần đọc shader và cảnh làm bằng `$SKILL/scripts/re/` (`SKILL` = thư mục skill này):

```bash
# tải bundle về để PHÂN TÍCH (không dùng lại), thư mục riêng, không commit
mkdir -p re/<site>/downloaded/js && curl -s -o re/<site>/downloaded/js/app.js <url app.js lấy từ 02-inspect-page.json>
node $SKILL/scripts/re/shaders.js re/<site>/downloaded/js/app.js > re/<site>/evidence/04-shaders.txt   # mọi chuỗi GLSL trong bundle
node $SKILL/scripts/re/scene.js re/<site>/downloaded/js/<chunk>.js                                     # cảnh nhúng dạng JSON.parse('...')
```

`scene.js` viết cho kiểu export của Finely (Unity xuất JSON nhét trong chunk JS). Web khác thì sửa chỗ tìm `JSON.parse('`.

Đo cảm giác cuộn của web mẫu để có số so sánh với bản mình: `python tools/capture_scroll.py <url> finely --setup=finely` (xem `pitfalls.md`, mục Đo).

## Báo cáo 3 ngăn

Lưu `re/<site>/bao-cao.md`. Mỗi dòng ghi rõ thuộc ngăn nào, không trộn:

```markdown
# <web mẫu>: vì sao nhìn thật

## Kết luận
3-5 câu. Công thức xếp theo mức quan trọng.

## Quan sát được (có file làm bằng chứng)
| Phát hiện | Bằng chứng (file, evidence_id, số shader) |

## Suy luận (hợp lý nhưng chưa có bằng chứng trực tiếp)
- ...

## Chưa rõ
- ...

## Vì sao bản cũ nhìn giả
| Triệu chứng | Nguyên nhân | Web mẫu xử lý |

## Bản quyền
JS, ảnh, model của web mẫu chỉ để phân tích. Không dùng lại.
```

Mẫu đã làm cho Finely Crafted: `finely-recipe.md`.
