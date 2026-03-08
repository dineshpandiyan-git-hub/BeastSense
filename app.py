import streamlit as st
import pandas as pd
import hashlib
import os
import cv2
import time
import pygame
from datetime import datetime
from collections import defaultdict
from ultralytics import YOLO

# ----- Setup -----
pygame.mixer.init()
alert_sound = "beep.mp3"
model = YOLO("yolov8m.pt")

CONFIDENCE_THRESHOLD = 0.3

ANIMALS_TO_TRACK = [
"bird","cat","dog","horse","sheep",
"cow","elephant","bear","zebra","giraffe"
]

os.makedirs("detections", exist_ok=True)

LOG_FILE = "detections_log.csv"

if not os.path.exists(LOG_FILE):
    pd.DataFrame(
        columns=["Time","Animal","Confidence","Image"]
    ).to_csv(LOG_FILE,index=False)

# ----- Auth Utils -----
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username,password,user_df):
    hashed_pw = hash_password(password)

    return not user_df[
        (user_df['username']==username) &
        (user_df['password']==hashed_pw)
    ].empty

def load_users():
    return pd.read_csv("users.csv") if os.path.exists("users.csv") else pd.DataFrame(columns=["username","password"])

def save_user(username,password):

    df = load_users()

    if username in df["username"].values:
        return False

    new_user = pd.DataFrame(
        [[username,hash_password(password)]],
        columns=["username","password"]
    )

    new_user.to_csv(
        "users.csv",
        mode='a',
        header=not os.path.exists("users.csv"),
        index=False
    )

    return True


# ----- Session State Init -----
if "authenticated" not in st.session_state:
    st.session_state.authenticated=False

if "username" not in st.session_state:
    st.session_state.username=""

if "running" not in st.session_state:
    st.session_state.running=False


# ----- Login Page -----
def login_page():

    st.markdown("""
    <h1 style='text-align:center;
    color:#1f8ef1;
    font-size:60px;
    font-weight:800;
    margin-bottom:10px;'>
    BeastSense
    </h1>

    <p style='text-align:center;
    font-size:20px;
    color:#6b7280;
    margin-bottom:30px;'>
    An AI-Powered Animal and Bird Detection & Tracking Platform
    </p>
    """, unsafe_allow_html=True)

    st.title("🔐 Login Page")

    tab1,tab2 = st.tabs(["🔑 Login","📝 Register"])

    with tab1:

        username = st.text_input("Username")

        password = st.text_input("Password",type="password")

        if st.button("Login"):

            users = load_users()

            if verify_user(username,password,users):

                st.success(f"Welcome {username}!")

                st.session_state.authenticated=True
                st.session_state.username=username

                st.rerun()

            else:
                st.error("Invalid username or password.")


    with tab2:

        new_user = st.text_input("New Username")

        new_pass = st.text_input("New Password",type="password")

        if st.button("Register"):

            if save_user(new_user,new_pass):

                st.success(
                    "Registration successful! You can now log in."
                )

            else:

                st.warning("Username already exists.")


# ----- Main App -----
def main_app():

    st.sidebar.success(
        f"👋 Logged in as: {st.session_state.username}"
    )

    if st.sidebar.button("🚪 Logout"):

        st.session_state.authenticated=False
        st.session_state.username=""

        st.rerun()


    st.markdown("""
    <h1 style='text-align:center;
    color:#1f8ef1;
    font-size:60px;
    font-weight:800;
    margin-bottom:0px;'>
    BeastSense
    </h1>

    <p style='text-align:center;
    font-size:22px;
    color:#374151;
    margin-top:5px;'>
    An AI-Powered Animal and Bird Detection & Tracking Platform
    </p>
    """, unsafe_allow_html=True)


    col1,col2 = st.sidebar.columns(2)

    with col1:
        if st.button("▶️ Start"):
            st.session_state.running=True

    with col2:
        if st.button("⏹️ Stop"):
            st.session_state.running=False


    enable_alerts = st.sidebar.checkbox(
        "🔔 Enable Sound Alerts",
        value=True
    )

    tab = st.sidebar.radio(
        "🧭 Navigation",
        ["Live Detection","Logs"]
    )


    if tab=="Live Detection":

        frame_placeholder = st.empty()

        if st.session_state.running:

            cap = cv2.VideoCapture(0)

            animal_count = defaultdict(int)

            last_detection_time = {}

            tracked_animals = {}

            next_object_id = 0

            frame_count = 0


            while cap.isOpened() and st.session_state.running:

                ret,frame = cap.read()

                if not ret:
                    st.error("❌ Failed to read from webcam.")
                    break


                results = model(frame)

                for r in results:

                    for box in r.boxes:

                        conf = box.conf[0].item()

                        if conf < CONFIDENCE_THRESHOLD:
                            continue

                        x1,y1,x2,y2 = map(int,box.xyxy[0])

                        cls = int(box.cls[0])

                        class_name = model.names[cls]


                        if class_name in ANIMALS_TO_TRACK:

                            center_x,center_y = (x1+x2)//2,(y1+y2)//2

                            found=False

                            for obj_id,(tx,ty) in tracked_animals.items():

                                if abs(tx-center_x)<50 and abs(ty-center_y)<50:

                                    tracked_animals[obj_id]=(center_x,center_y)

                                    found=True

                                    break


                            if not found:

                                tracked_animals[next_object_id]=(center_x,center_y)

                                next_object_id+=1

                                animal_count[class_name]+=1


                                if class_name not in last_detection_time or time.time()-last_detection_time[class_name]>5:

                                    if enable_alerts and os.path.exists(alert_sound):

                                        pygame.mixer.Sound(alert_sound).play()


                                    last_detection_time[class_name]=time.time()


                                    timestamp=datetime.now().strftime("%Y-%m-%d %H-%M-%S")

                                    image_name=f"detections/{class_name}_{frame_count}.jpg"

                                    cv2.imwrite(image_name,frame)


                                    pd.DataFrame(
                                        [[timestamp,class_name,conf,image_name]],
                                        columns=["Time","Animal","Confidence","Image"]
                                    ).to_csv(
                                        LOG_FILE,
                                        mode='a',
                                        header=False,
                                        index=False
                                    )


                        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)

                        cv2.putText(
                            frame,
                            f"{class_name} {conf:.2f}",
                            (x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0,255,0),
                            2
                        )


                y_offset=30

                for animal,count in animal_count.items():

                    cv2.putText(
                        frame,
                        f"{animal}: {count}",
                        (10,y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0,255,255),
                        2
                    )

                    y_offset+=30


                frame_rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

                frame_placeholder.image(
                    frame_rgb,
                    channels="RGB",
                    use_container_width=True
                )

                frame_count+=1


            cap.release()

            st.warning("⛔ Detection stopped.")

        else:

            st.info("Click ▶️ Start to begin detection.")


    elif tab=="Logs":

        st.header("📜 Detection Logs")

        if os.path.exists(LOG_FILE):

            df=pd.read_csv(LOG_FILE)

            st.dataframe(
                df.tail(20),
                use_container_width=True
            )

            with open(LOG_FILE,"rb") as f:

                st.download_button(
                    "📥 Download Log CSV",
                    f,
                    file_name="detections_log.csv"
                )

        else:

            st.info("No logs found yet.")


    st.sidebar.markdown("### 🖼️ Image Gallery")

    if os.path.exists("detections"):

        images=sorted(
            os.listdir("detections"),
            reverse=True
        )[:5]

        for img in images:

            img_path=os.path.join("detections",img)

            st.sidebar.image(
                img_path,
                caption=img,
                use_container_width=True
            )


# ----- Run App -----
if st.session_state.authenticated:
    main_app()
else:
    login_page()