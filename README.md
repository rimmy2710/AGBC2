Trợ lí tin tức AI (AI news assistant)
Vấn đề thực tế: 
Hiện nay, lượng thông tin trên Internet ngày càng quá tải và thiếu tính phù hợp cho từng cá nhân. Người dùng mong muốn chọn nội dung chất lượng, theo đúng mong muốn/nhu cầu cá nhân  mà ko mất quá nhiều thời gian để tìm/đọc/tổng hợp. 
AI bot giúp lọc đúng thông tin quan trọng từ các kênh thông tin chính thống, cài đặt thời gian tổng hợp, thông báo (ví dụ 7h hàng ngày hoặc cập nhật theo thời gian thực), giúp người dùng tối ưu thời gian và công sức mà vẫn theo dõi hiệu quả các thông tin trên Internet (theo nhu cầu cá nhân)
Giống như 1 trợ lí tin tức thời đại 4.0
Nhu cầu
Là người vận hành content, tôi muốn gửi link/tin nhắn nguồn vào Telegram/X để bot ghi nhận và lưu.
Tôi muốn cấu hình các chủ đề cần theo dõi (vd: BTC, AI tokens, regulations, ETF, funding, hacks…) để bot lọc và chỉ giữ tin relevant (tránh viết các tin quá rác hoặc lạc đề)
Tôi muốn bot tóm tắt + viết lại theo tone tôi yêu cầu (LinkedIn professional / Binance Square trader / Telegram casual / neutral news…) và xuất ra Sheet/Excel để tôi duyệt.
Sau khi tôi duyệt “Approved”, bot có thể đăng (ở phase sau) hoặc tạo “ready-to-post” format.
Mục tiêu sản phẩm
 Xây 1 bot “News Ops” có khả năng:
Đọc tin từ các nguồn bạn cung cấp (X, Telegram)
Lọc tin theo chủ đề/tiêu chí chất lượng để giảm spam
Soạn tin theo văn phong yêu cầu, tạo bản nháp để xem review (xuất Excel/Google Sheets)
(Giai đoạn sau) Đăng tin lên các kênh social và trang website (tôi sở hữu) mặc định
Note
Văn phong tự nhiên như người viết, không văn mẫu (sẽ có tiêu chuẩn đầu vào cho bot học)
Không bịa số liệu 
Hỗ trợ nhiều tone, ví dụ:
telegram_casual: ngắn, đời, dễ đọc
linkedin_pro: chuyên nghiệp, insight
neutral_news: trung lập, facts
Có thể tạo 2 version: short / long (optional)
HỆ THỐNG GIÚP ADMIN LÀM GÌ?
Trước đây (Manual)
Tự lướt X / Telegram
Tự lọc tin quan trọng
Tự viết lại từng bài
Dễ trùng, dễ sót tin
Sau khi có bot
Tin được cập nhật tự động
Không trùng lặp
Nội dung đồng nhất văn phong
Admin chỉ cần duyệt & đăng

Luồng xử lý (Pipeline) đề xuất
Step 1 – Read (Ingest)
Nhận input → extract text, author, url, timestamp
Check trùng lặp (hash/similarity)
Lưu DB với status = RAW
Step 2 – Filter
Lọc theo:
Chủ đề admin khai báo (keyword + semantic)
Spam / rác / clickbait / airdrop
Độ uy tín nguồn
Chấm quality_score (0–100)
Pass → QUALIFIED, Fail → REJECTED (có lý do)
Step 3 – Write (Compose)
Tạo:
Summary bullet (facts only)
Draft bài viết theo tone cấu hình
Hashtag + CTA (nếu cần)
Ghi ra Google Sheets / Excel
Trạng thái = Draft
ĐỀ XUẤT THÊM OUTPUT ( NẾU CÓ THỂ) :
 Output = Publish + Notify + Report (theo lịch)
Publish: Đăng bài trên Website, Social, Channel, Binance Square
Notify: Thông báo tin tức cá nhân hóa
Report: Tổng hợp tin tức cá nhân hóa
