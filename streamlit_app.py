import streamlit as st
from src.analyzer import DraftAnalyzer


def analyze_image_bytes(image_bytes, pass_threshold):
    analyzer = DraftAnalyzer(image_bytes)
    analyzer.analyze()
    return analyzer.get_analysis_summary(pass_threshold=pass_threshold)


st.set_page_config(
    page_title='Draft Angle Checker',
    page_icon='🧪',
    layout='centered'
)

st.title('Draft Angle Checker')
st.write(
    'Upload a CATIA Draft Analysis screenshot and get a pass/fail summary for the draft angles.'
)

uploaded_file = st.file_uploader('Choose an image file', type=['png', 'jpg', 'jpeg', 'bmp', 'tiff'])
threshold = st.slider('Pass threshold (%)', min_value=0, max_value=100, value=80)

if uploaded_file is not None:
    image_bytes = uploaded_file.read()
    try:
        summary = analyze_image_bytes(image_bytes, pass_threshold=threshold)
        status = summary['status']
        st.image(image_bytes, caption='Uploaded Image', use_column_width=True)
        st.markdown('---')
        if status == 'PASS':
            st.success(f"OK — Draft angle passes with {summary['pass_percentage']:.2f}% green pixels.")
        else:
            st.error(f"NOT OK — Draft angle fails with {summary['fail_percentage']:.2f}% red pixels.")

        st.subheader('Analysis Summary')
        st.json(summary)
    except Exception as exc:
        st.error(f'Analysis failed: {exc}')
