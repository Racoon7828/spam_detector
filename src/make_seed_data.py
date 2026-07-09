"""
한국어 '이메일' 합성 데이터 생성기 (정상+스팸, 동일 이메일 문체).

목적: 실제 데이터의 '채널 편향'(정상=알림톡 / 스팸=이메일제목) 을 깨기 위해,
      같은 이메일 형식의 정상·스팸을 만들어 모델이 '문체'가 아닌 '내용'으로
      구분하도록 강제한다.

출력 (겹치지 않게 분리):
    data/korean_synth.csv   (label,text)  - 학습용
    data/demo_samples.csv   (label,text,lang) - 데모/비교용(학습 미사용)

실행: python src/make_seed_data.py
"""
import os
import sys
import csv
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.preprocessing import compose_email

random.seed(42)

# 첨부파일: 정상=안전 확장자 / 스팸=위험 확장자 (일부 겹침으로 '첨부=스팸' 편향 방지)
# 빈 문자열 다수 -> 약 40%만 첨부 있음
HAM_ATTACH = ["", "", "", "보고서.pdf", "명세서.pdf", "일정표.xlsx", "계약서.docx", "사진.jpg", "안내문.pdf"]
SPAM_ATTACH = ["", "", "", "청구서.exe", "송장.html", "당첨안내.zip", "안내문.docx", "invoice.exe", "photo.scr"]

SLOTS = {
    "회사": ["네이버", "카카오", "쿠팡", "국민은행", "신한카드", "토스", "우체국", "넷플릭스", "배달의민족", "롯데카드"],
    "금액": ["300만원", "5000만원", "1억원", "최대 2억원", "3천만원", "500만원"],
    "이율": ["연 2.9%", "최저금리", "무이자 6개월", "저금리 대환", "연 3.5%"],
    "할인": ["최대 90%", "80%", "반값", "1+1", "70%"],
    "상품": ["명품 가방", "겨울 패딩", "건강식품", "가전제품", "프리미엄 시계", "노트북"],
    "보험": ["치매보험", "암보험", "치아보험", "종합건강보험", "실손보험"],
    "보험사": ["라이나생명", "AIA생명", "삼성화재", "메리츠화재"],
    "이름": ["김민수", "이지은", "박영호", "최수빈", "정예린", "한지훈"],
    "직책": ["팀장님", "과장님", "대리님", "부장님", "선생님", "책임님"],
    "부서": ["마케팅팀", "개발팀", "인사팀", "영업팀", "기획팀", "총무팀"],
    "요일": ["월요일", "이번 주 금요일", "다음 주 화요일", "오는 목요일", "내일"],
    "시간": ["오전 10시", "오후 2시", "오후 4시", "내일 오전", "오후 5시"],
    "문서": ["3분기 실적 보고서", "회의록", "제안서 초안", "예산안", "프로젝트 계획서", "결산 자료"],
    "링크": ["http://bit.ly/xz39", "vvw.event-win.co.kr", "han.gl/Qz7", "goo.gl/aB2p", "me2.do/kk1"],
    "상금": ["500만원", "아이폰", "해외여행 상품권", "1000만원", "백화점 상품권"],
    "기관": ["국세청", "질병관리청", "건강보험공단", "보건소", "행정복지센터"],
    "행사": ["건강강좌", "예방접종", "직거래장터", "환경한마당", "평생학습 강좌"],
    "카지노": ["바카라", "슬롯", "홀덤", "룰렛"],
}


def fill(t: str, slots: dict) -> str:
    for key, values in slots.items():
        token = "{" + key + "}"
        while token in t:
            t = t.replace(token, random.choice(values), 1)
    return t


# 링크는 라벨과 무관하게 부착한다(아래 gen_pool). 템플릿엔 {링크}를 넣지 않음.
# (제목, 본문) — 스팸: 대출/보험/도박/피싱/광고/투자/당첨
SPAM = [
    ("{할인} 할인 특가 이벤트", "회원님만을 위한 {상품} {할인} 특별 할인! 지금 구매하세요"),
    ("[{회사}] 계정 보안 확인 필요", "비정상 로그인이 감지되었습니다. 본인 확인을 위해 즉시 로그인하세요"),
    ("결제가 실패하였습니다", "고객님 결제 정보에 문제가 있습니다. 정보를 업데이트해 주세요"),
    ("배송 정보를 확인해 주세요", "{회사} 배송 주소가 일치하지 않습니다. 재입력 바랍니다"),
    ("저금리 대출 안내", "{금액}까지 {이율} 대출 가능합니다. 지금 바로 상담 신청하세요"),
    ("무직자 주부 대출 가능", "신용등급 상관없이 {금액} 당일 승인. 지금 전화 문의 주세요"),
    ("(광고) {보험} 가입 안내", "{보험사} {보험} 첫날부터 100% 보장! 지금 보험료를 확인하세요"),
    ("(광고) 평생 간병비 보장", "{보험사} {보험}으로 노후를 준비하세요. 무료 상담 신청 받습니다"),
    ("투자 정보 무료 공개", "이번 달 수익률 300% 종목 무료 공개! 리딩방으로 지금 입장하세요"),
    ("급등주 내부정보 입수", "지금 사면 10배 수익 보장. 무료 추천주 받아가세요"),
    ("축하합니다 당첨되셨습니다", "귀하가 경품 이벤트에 당첨되어 {상금}을 드립니다. 지금 연락 주세요"),
    ("[긴급] 카드 승인 알림", "해외에서 카드가 승인되었습니다. 본인이 아니면 즉시 확인 바랍니다"),
    ("{카지노} 신규가입 이벤트", "지금 가입하면 첫 충전 10만원 지급! 바로 접속하세요"),
    ("한정 수량 특가 마감 임박", "{상품} 재고 소진 임박! 오늘 자정 마감이니 지금 주문하세요"),
    ("정부 지원금 신청 안내", "귀하는 지원금 대상자입니다. 기한 내에 꼭 신청하세요"),
    ("성인 전용 무료 이벤트", "지금 무료로 만나보세요. 즉시 입장 가능합니다"),
]

# (제목, 본문) — 정상: 업무/알림/공공안내/개인/구독 (동일 이메일 문체)
HAM = [
    ("{문서} 검토 요청", "{직책}, 첨부한 {문서} 검토 부탁드립니다. 의견 주시면 반영하겠습니다."),
    ("{요일} {부서} 회의 안내", "{부서} 회의를 {요일} {시간}에 진행합니다. 참석 부탁드립니다."),
    ("자료 공유드립니다", "{이름}입니다. 요청하신 {문서} 파일 링크로 공유드립니다. 확인 부탁드려요."),
    ("[{회사}] 주문 배송 시작", "주문하신 상품의 배송이 시작되었습니다. 배송조회 링크를 확인하세요."),
    ("[{회사}] 결제 영수증", "이용해 주셔서 감사합니다. 결제가 정상 완료되어 영수증 링크를 보내드립니다."),
    ("예약이 확정되었습니다", "{요일} {시간} 예약이 정상 확정되었습니다. 방문 감사합니다."),
    ("[{기관}] {행사} 안내", "{기관}입니다. {행사}를 {요일}에 운영합니다. 아래 링크에서 신청 바랍니다."),
    ("[{기관}] {행사} 접수 완료", "신청하신 {행사} 접수가 완료되었습니다. 자세한 사항은 링크를 참고하세요."),
    ("지난번 도움 감사드립니다", "{직책} 덕분에 {문서}를 잘 마무리했습니다. 진심으로 감사드립니다."),
    ("일정 조율 문의", "{직책}, {요일} {시간}에 미팅 가능하신지 회신 부탁드립니다."),
    ("{회사} 월간 뉴스레터", "이번 달 주요 소식과 업데이트를 아래 링크로 안내드립니다. 감사합니다."),
    ("가입을 환영합니다", "{회사} 가입을 환영합니다. 서비스 이용 안내 링크를 보내드립니다."),
    ("{문서} 최종본 전달", "{이름}입니다. {문서} 최종본 전달드립니다. 확인 후 회신 부탁드립니다."),
    ("{행사} 일정 변경 안내", "{기관}입니다. {행사} 일정이 {요일}로 변경되었습니다. 참고 부탁드립니다."),
    ("문의 주신 건 답변드립니다", "안녕하세요 {이름}입니다. 문의하신 내용 확인하여 답변드립니다. 추가 문의는 회신 주세요."),
    ("{부서} 업무 협조 요청", "{직책}, {문서} 관련하여 협조 부탁드립니다. {요일}까지 회신 주시면 감사하겠습니다."),
    # --- 정상 배송/주문/결제 알림 (스팸의 '배송/결제' 단어 편향 완화) ---
    ("[{회사}] 배송 완료 안내", "주문하신 상품이 배송 완료되었습니다. 이용해 주셔서 감사합니다."),
    ("[{회사}] 상품 발송 안내", "주문하신 상품이 오늘 발송되었습니다. {요일} 도착 예정입니다."),
    ("택배 도착 예정 안내", "주문하신 택배가 {요일} 도착 예정입니다. 부재 시 문 앞에 두겠습니다."),
    ("[{회사}] 배송 지연 안내", "상품 배송이 다소 지연되고 있어 안내드립니다. 양해 부탁드립니다."),
    ("[{회사}] 주문이 접수되었습니다", "주문이 정상 접수되었습니다. 주문 내역과 배송 일정을 확인해 주세요."),
    ("[{회사}] 결제 완료 안내", "요청하신 결제가 정상 완료되었습니다. 주문번호를 확인해 주세요."),
    ("[{회사}] 반품 접수 완료", "요청하신 반품이 정상 접수되었습니다. 수거 예정일을 안내드립니다."),
    ("[{회사}] 카드 이용 안내", "{시간}에 카드 결제가 정상 승인되었습니다. 이용 내역을 확인하세요."),
    # --- 개인 안부/인사 (약한 카테고리 보강) ---
    ("생일 축하해", "{이름}아 생일 진심으로 축하해! 좋은 하루 보내고 조만간 얼굴 보자."),
    ("명절 인사드립니다", "{직책} 즐거운 명절 보내세요. 늘 감사드리며 새해 복 많이 받으세요."),
    ("오랜만이야", "{이름}아 잘 지내지? 오랜만에 연락해. 시간 되면 {요일}에 밥 한번 먹자."),
    ("고마웠어", "{이름}아 지난번엔 정말 고마웠어. 덕분에 잘 해결했어. 다음엔 내가 살게."),
    ("잘 도착했습니다", "{직책} 방금 잘 도착했습니다. 오늘 챙겨주셔서 감사했습니다. 편히 쉬세요."),
    ("안부 인사드립니다", "{직책} 요즘 잘 지내시죠? 오랜만에 안부 여쭙니다. 조만간 한번 뵙고 싶습니다."),
    ("결혼 소식 전합니다", "{이름}입니다. 다름이 아니라 {요일}에 결혼하게 되어 소식 전해요. 꼭 와주세요."),
    ("주말에 뭐 해", "{이름}아 이번 {요일}에 시간 괜찮아? 오랜만에 같이 영화라도 보러 가자."),
]


# ====== 영어 합성 (실제 SpamAssassin의 부족한 거래/개인 메일 보강) ======
EN_SLOTS = {
    "name": ["John", "Sarah", "Michael", "Emily", "David", "Anna", "Chris", "Laura"],
    "company": ["Amazon", "PayPal", "Netflix", "Chase", "Apple", "eBay", "FedEx", "Uber"],
    "day": ["Monday", "Friday", "next Tuesday", "this weekend", "tomorrow"],
    "time": ["10 am", "2 pm", "3:30 pm", "9 am", "noon"],
    "doc": ["quarterly report", "project plan", "meeting notes", "budget proposal", "contract"],
    "num": ["48213", "90577", "12094", "33481"],
    "prize": ["one million dollars", "a free iPhone", "a gift card", "a luxury vacation"],
    "amount": ["five thousand dollars", "twenty thousand dollars", "fifty thousand dollars"],
    "pct": ["seventy percent", "ninety percent", "three hundred percent"],
}
EN_LINKS = ["http://bit.ly/x9f2", "www.claim-now.co", "goo.gl/pR7k", "http://secure-verify.net"]

EN_HAM = [
    ("Your order has shipped", "Hi {name}, your order {num} has shipped and will arrive by {day}. Thank you for shopping with us."),
    ("Order confirmation", "Thank you for your purchase. Your order {num} has been confirmed and is being prepared for shipment."),
    ("Appointment confirmed", "Your appointment is confirmed for {time} on {day}. Please arrive ten minutes early."),
    ("Payment receipt", "Thank you for your payment. Your receipt for order {num} is attached for your records."),
    ("Your invoice from {company}", "Please find your monthly invoice attached. Thank you for being a valued customer."),
    ("Happy birthday", "Hi {name}, happy birthday! Hope you have a wonderful day. Let us catch up soon."),
    ("Thank you", "Hi {name}, thank you so much for your help with the {doc}. I really appreciate it."),
    ("Meeting on {day}", "Hi {name}, can we meet on {day} at {time} to go over the {doc}? Let me know if that works."),
    ("{doc} for review", "Hi {name}, please find the {doc} attached for your review. I would appreciate your feedback by {day}."),
    ("Reservation confirmed", "Your reservation for {day} at {time} is confirmed. We look forward to seeing you."),
    ("{company} monthly newsletter", "Here is our monthly newsletter with the latest news and updates. Thank you for subscribing."),
    ("Welcome to {company}", "Welcome aboard {name}. Your account is ready. Here is a quick guide to getting started."),
    ("Following up", "Hi {name}, just following up on the {doc}. Please let me know if you need anything else."),
    ("Delivery update", "Your package {num} is out for delivery and should arrive {day}. No action is needed."),
]

EN_SPAM = [
    ("You have won", "Congratulations {name}, you have won {prize}. Claim your reward now before it expires."),
    ("Cheap meds online", "Buy cheap medication online with no prescription needed. Save {pct} on your first order today."),
    ("Loan pre approved", "You are pre approved for a {amount} loan at the lowest rate. Apply now and get funds today."),
    ("Security alert from {company}", "We detected unusual activity on your account. Verify your identity immediately to avoid suspension."),
    ("Your payment failed", "Your recent payment could not be processed. Update your billing information now to continue service."),
    ("Hot stock tip", "This stock is about to explode {pct}. Join our free trading room and start earning now."),
    ("Work from home", "Earn {amount} per week working from home. No experience needed. Start today and get paid weekly."),
    ("Final notice", "This is your final notice. Claim {prize} now or lose it forever. Act immediately."),
    ("You are a winner", "You have been selected to receive {prize}. Reply with your details to claim your prize."),
    ("Weight loss miracle", "Lose weight fast with this miracle pill. Guaranteed results or your money back. Order now."),
    ("Verify your account", "Your {company} account will be closed. Confirm your password and card number to keep it active."),
    ("Exclusive offer", "Get {pct} off luxury watches today only. Limited stock. Buy now before it sells out."),
]


def gen_pool(pairs, label, n, slots, links, link_prob=0.5, attach_list=None):
    """제목+본문(+첨부)을 compose_email로 합침. 링크는 라벨 무관 ~50% 부착.
    attach_list 지정 시 라벨별 첨부를 붙여 확장자 신호 학습."""
    rows, seen, attempts = [], set(), 0
    while len(rows) < n and attempts < n * 60:
        attempts += 1
        subject, body = random.choice(pairs)
        att = random.choice(attach_list) if attach_list else ""
        text = compose_email(subject=fill(subject, slots),
                             body=fill(body, slots), attachment=att)
        if random.random() < link_prob:                 # 정상·스팸 모두 ~50%
            text += " " + random.choice(links)
        if text in seen:
            continue
        seen.add(text)
        rows.append((label, text))
    return rows


def main():
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic"
    )
    os.makedirs(data_dir, exist_ok=True)

    def split_write(pairs_spam, pairs_ham, slots, links,
                    n=700, n_demo=60, attach_spam=None, attach_ham=None):
        spam = gen_pool(pairs_spam, "spam", n, slots, links, attach_list=attach_spam)
        ham = gen_pool(pairs_ham, "ham", n, slots, links, attach_list=attach_ham)
        demo = spam[:n_demo] + ham[:n_demo]      # 학습과 겹치지 않게 앞부분만 데모로
        train = spam[n_demo:] + ham[n_demo:]
        random.shuffle(train); random.shuffle(demo)
        return train, demo

    # 한국어 합성 (첨부 포함: 정상=안전확장자 / 스팸=위험확장자)
    ko_train, ko_demo = split_write(SPAM, HAM, SLOTS, SLOTS["링크"],
                                    attach_spam=SPAM_ATTACH, attach_ham=HAM_ATTACH)
    # 영어 합성 (현재 미사용, 영어모델용 보관)
    en_train, en_demo = split_write(EN_SPAM, EN_HAM, EN_SLOTS, EN_LINKS)

    def write_csv(path, rows, with_lang=None):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if with_lang:
                w.writerow(["label", "text", "lang"])
                for label, text in rows:
                    w.writerow([label, text, with_lang])
            else:
                w.writerow(["label", "text"])
                w.writerows(rows)

    write_csv(os.path.join(data_dir, "korean_synth.csv"), ko_train)
    write_csv(os.path.join(data_dir, "english_synth.csv"), en_train)
    # 데모: 한국어 전용 (현재 모델이 한국어 전용이므로). 학습 미사용.
    # en_demo 는 영어 모델 추가 시 사용 예정.
    demo_path = os.path.join(data_dir, "demo_samples.csv")
    with open(demo_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["label", "text", "lang"])
        for label, text in ko_demo:
            w.writerow([label, text, "ko"])

    print(f"[한국어 합성] korean_synth.csv: {len(ko_train)}건")
    print(f"[영어 합성]   english_synth.csv: {len(en_train)}건 (현재 미사용, 영어모델용 보관)")
    print(f"[데모]        demo_samples.csv: {len(ko_demo)}건 (한국어, 학습 미사용)")


if __name__ == "__main__":
    main()
