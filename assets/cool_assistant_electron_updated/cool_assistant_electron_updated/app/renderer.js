const assistant = document.querySelector("#assistant");
const bubble = document.querySelector("#bubble");
const buttons = [...document.querySelectorAll("[data-pose]")];

const poses = {
  idle: {
    image: "assets/idle.png",
    alt: "기본 대기 중인 쿨 비서",
    message: "무엇을 도와드릴까요?",
    animation: "breathe"
  },
  sleep: {
    image: "assets/sleep.png",
    alt: "잠들어 있는 쿨 비서",
    message: "잠시 에너지를 충전하고 있어요… Zzz",
    animation: "sleep"
  },
  schedule: {
    image: "assets/schedule.png",
    alt: "일정을 정리하는 쿨 비서",
    message: "오늘 일정을 차근차근 정리해 볼게요.",
    animation: "write"
  },
  surprise: {
    image: "assets/surprise.png",
    alt: "깜짝 놀란 쿨 비서",
    message: "앗! 중요한 알림이 있어요!",
    animation: "pop"
  }
};

let currentPose = "idle";
let bubbleTimer;
let idleTimer;

function showBubble(text, duration = 2600) {
  bubble.textContent = text;
  bubble.classList.add("show");
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => bubble.classList.remove("show"), duration);
}

function resetIdleTimer() {
  clearTimeout(idleTimer);
  // 30초 동안 상호작용이 없으면 자동으로 잠듭니다.
  idleTimer = setTimeout(() => setPose("sleep"), 30000);
}

function setPose(name) {
  const pose = poses[name];
  if (!pose) return;

  currentPose = name;
  assistant.src = pose.image;
  assistant.alt = pose.alt;
  assistant.className = "";
  void assistant.offsetWidth;
  assistant.classList.add(pose.animation);

  buttons.forEach(button => {
    button.classList.toggle("active", button.dataset.pose === name);
  });

  showBubble(pose.message, name === "sleep" ? 3200 : 2400);
  resetIdleTimer();

  if (name === "surprise") {
    setTimeout(() => {
      if (currentPose === "surprise") setPose("idle");
    }, 2600);
  }
}

buttons.forEach(button => {
  button.addEventListener("click", () => setPose(button.dataset.pose));
});

assistant.addEventListener("click", () => {
  const order = ["idle", "schedule", "surprise", "sleep"];
  const next = order[(order.indexOf(currentPose) + 1) % order.length];
  setPose(next);
});

assistant.addEventListener("dblclick", () => setPose("surprise"));

document.addEventListener("keydown", event => {
  const shortcuts = { "1": "idle", "2": "sleep", "3": "schedule", "4": "surprise" };
  if (shortcuts[event.key]) setPose(shortcuts[event.key]);
});

document.querySelector("#hideButton").addEventListener("click", () => {
  window.desktopAPI?.hide();
});

document.querySelector("#quitButton").addEventListener("click", () => {
  window.desktopAPI?.quit();
});

setPose("idle");
