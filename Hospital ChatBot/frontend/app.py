import requests
import streamlit as st


API_URL = "http://localhost:8001"


st.set_page_config(
    page_title="ABC Hospital",
    page_icon="🏥",
    layout="wide"
)


if "messages" not in st.session_state:

    st.session_state.messages = []


st.title("🏥 ABC Multispeciality Hospital")

st.caption(
    "Official Hospital Virtual Assistant"
)


with st.sidebar:

    st.header("Hospital Assistant")

    st.write(
        """
        I can help you with:

        - 👨‍⚕️ Doctors
        - 🏥 Departments
        - 📅 Appointments
        - 🕐 Available slots
        - 💳 Insurance
        - 📋 Hospital information
        """
    )

    if st.button("Clear conversation"):

        st.session_state.messages = []

        st.rerun()


for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


user_message = st.chat_input(
    "Ask about doctors, appointments or insurance..."
)


if user_message:

    with st.chat_message("user"):

        st.markdown(
            user_message
        )

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    try:

        response = requests.post(
            f"{API_URL}/chat",
            json={
                "message": user_message,
                "history": st.session_state.messages
            },
            timeout=60
        )

        if response.status_code != 200:

            answer = (
                "Sorry, the hospital assistant "
                "is temporarily unavailable."
            )

        else:

            data = response.json()

            answer = data["answer"]

    except requests.exceptions.RequestException:

        answer = (
            "I couldn't connect to the hospital "
            "assistant backend. Please make sure "
            "FastAPI is running."
        )

    with st.chat_message("assistant"):

        st.markdown(answer)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )
