import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime
import base64
from io import BytesIO
import plotly.io as pio
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import tempfile
import os
from fpdf import FPDF

# Constants
CHART_HEIGHT = 600
COLOR_MAP = {
    'Cá nhân Khớp Ròng': '#1f77b4',
    'Nước ngoài Khớp Ròng': '#ff7f0e',
    'Tổ chức trong nước Khớp Ròng': '#2ca02c',
    'Tự doanh Khớp Ròng': '#d62728',
    'Cá nhân Thỏa thuận Ròng': '#1f77b4',
    'Nước ngoài Thỏa thuận Ròng': '#ff7f0e',
    'Tổ chức trong nước Thỏa thuận Ròng': '#2ca02c',
    'Tự doanh Thỏa thuận Ròng': '#d62728'
}

# Đường dẫn file CSV
DATA_PATH = r'C:\MyProject\combined_data.csv'
MARKETCAP_PATH = r'C:\MyProject\Vietnam_Marketcap_cleaned.csv'
VOLUME_PATH = r"C:\MyProject\Vietnam_volume_cleaned.csv"
PRICE_PATH = r"C:\MyProject\Vietnam_Price_cleaned.csv"
SECTOR_PATH = r"C:\MyProject\Phan_loai_nganh.csv"
# Đường dẫn file CSV từ GitHub (định dạng raw)
#VOLUME_PATH = 'https://raw.githubusercontent.com/ThuyTien121/GPM1-ASSIGNMENT3/main/Vietnam_volume_cleaned.csv'
#PRICE_PATH = 'https://raw.githubusercontent.com/ThuyTien121/GPM1-ASSIGNMENT3/main/Vietnam_Price_cleaned.csv'
#SECTOR_PATH = 'https://raw.githubusercontent.com/ThuyTien121/GPM1-ASSIGNMENT3/main/Phan_loai_nganh.csv'
#MARKETCAP_PATH = 'https://raw.githubusercontent.com/ThuyTien121/GPM1-ASSIGNMENT3/main/Vietnam_Marketcap_cleaned.csv'


# Thiết lập trang
st.set_page_config(page_title="Dashboard Giao dịch và Thị trường", layout="wide")

# Hàm tải dữ liệu từ file thứ nhất (Market)
@st.cache_data
def load_and_prepare_data(volume_path, price_path, sector_path, marketcap_path):
    """Đọc CSV dạng wide → long, merge, tính TradeValue, trả về df_trade và df_marketcap."""
    def read_volume_wide(file_path):
        chunk_list = []
        for chunk in pd.read_csv(file_path, iterator=True, chunksize=50000):
            chunk = chunk.melt(id_vars=['Name', 'Code'], var_name='Date', value_name='Volume')
            chunk['Date'] = pd.to_datetime(chunk['Date'], format='%d-%m-%Y', errors='coerce')
            chunk_list.append(chunk)
        return pd.concat(chunk_list, ignore_index=True) if chunk_list else pd.DataFrame(columns=['Name', 'Code', 'Date', 'Volume'])
    
    def read_price_wide(file_path):
        chunk_list = []
        for chunk in pd.read_csv(file_path, iterator=True, chunksize=50000):
            chunk = chunk.melt(id_vars=['Name', 'Code'], var_name='Date', value_name='Close')
            chunk['Date'] = pd.to_datetime(chunk['Date'], format='%d-%m-%Y', errors='coerce')
            chunk_list.append(chunk)
        return pd.concat(chunk_list, ignore_index=True) if chunk_list else pd.DataFrame(columns=['Name', 'Code', 'Date', 'Close'])
    
    def read_marketcap_wide(file_path):
        chunk_list = []
        for chunk in pd.read_csv(file_path, iterator=True, chunksize=50000):
            chunk = chunk.melt(id_vars=['Name', 'Code'], var_name='Date', value_name='MarketCap')
            chunk['Date'] = pd.to_datetime(chunk['Date'], format='%d-%m-%Y', errors='coerce')
            chunk_list.append(chunk)
        return pd.concat(chunk_list, ignore_index=True) if chunk_list else pd.DataFrame(columns=['Name', 'Code', 'Date', 'MarketCap'])
    
    df_volume = read_volume_wide(volume_path)
    df_price = read_price_wide(price_path)
    df_marketcap = read_marketcap_wide(marketcap_path)
    df_sector = pd.read_csv(sector_path)
    if 'Mã' in df_sector.columns:
        df_sector.rename(columns={'Mã': 'Code'}, inplace=True)
    
    df_trade = pd.merge(df_price, df_volume, on=['Date', 'Code'], how='inner')
    df_trade = pd.merge(df_trade, df_sector, on='Code', how='left')
    df_trade['TradeValue'] = df_trade['Close'] * df_trade['Volume'] / 1e9
    df_trade.dropna(subset=['TradeValue'], inplace=True)
    if 'Ngành ICB - cấp 1' in df_trade.columns:
        df_trade.rename(columns={'Ngành ICB - cấp 1': 'Industry'}, inplace=True)
    
    df_marketcap = pd.merge(df_marketcap, df_sector, on='Code', how='left')
    df_marketcap.dropna(subset=['MarketCap'], inplace=True)
    if 'Ngành ICB - cấp 1' in df_marketcap.columns:
        df_marketcap.rename(columns={'Ngành ICB - cấp 1': 'Industry'}, inplace=True)
    
    return df_trade, df_marketcap, df_price

# Hàm tải dữ liệu từ file thứ hai (Tổng quan và Chi tiết)
@st.cache_data
def load_data():
    """Đọc và chuẩn bị dữ liệu từ tệp CSV."""
    df = pd.read_csv(DATA_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

# Hàm tạo PDF từ biểu đồ
def export_charts_to_pdf(charts):
    with tempfile.TemporaryDirectory() as tmpdirname:
        image_paths = []
        for name, fig in charts.items():
            # Cập nhật theme và màu sắc của biểu đồ
            fig.update_layout(template="plotly_white", font=dict(size=12, color="black"))
            img_path = os.path.join(tmpdirname, f"{name}.png")
            fig.write_image(img_path, format="png", width=1100, height=600, scale=2)
            image_paths.append(img_path)
        
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        for img_path in image_paths:
            pdf.add_page()
            img_width = 277
            img_height = img_width * (600 / 1100)
            if img_height > 190:
                img_height = 190
                img_width = img_height * (1100 / 600)
            pdf.image(img_path, x=(297 - img_width) / 2, y=(210 - img_height) / 2, w=img_width, h=img_height)
        
        return pdf.output(dest="S").encode("latin1")

# Hàm lọc dữ liệu
def filter_data_by_date(df, start_date, end_date):
    """Lọc dữ liệu theo khoảng thời gian."""
    start_date = pd.to_datetime(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59, microsecond=999999)
    return df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

# Hàm chuẩn bị dữ liệu cho biểu đồ khớp
def prepare_khop_data(filtered_df):
    """Chuẩn bị dữ liệu cho biểu đồ giao dịch khớp lệnh."""
    khop_data = filtered_df.groupby('Ngành').agg({
        'Cá nhân Khớp Ròng': 'sum',
        'Nước ngoài Khớp Ròng': 'sum',
        'Tổ chức trong nước Khớp Ròng': 'sum',
        'Tự doanh Khớp Ròng': 'sum'
    }).reset_index()
    khop_data['Tổng'] = khop_data['Cá nhân Khớp Ròng'] + khop_data['Nước ngoài Khớp Ròng'] + \
                        khop_data['Tổ chức trong nước Khớp Ròng'] + khop_data['Tự doanh Khớp Ròng']
    khop_data = khop_data.sort_values(by='Tổng', ascending=False)
    return pd.melt(
        khop_data,
        id_vars=['Ngành'],
        value_vars=['Cá nhân Khớp Ròng', 'Nước ngoài Khớp Ròng', 'Tổ chức trong nước Khớp Ròng', 'Tự doanh Khớp Ròng'],
        var_name='Nhà đầu tư',
        value_name='Giá trị'
    )

# Hàm chuẩn bị dữ liệu cho biểu đồ thỏa thuận
def prepare_thoathuan_data(filtered_df):
    """Chuẩn bị dữ liệu cho biểu đồ giao dịch thỏa thuận."""
    thoathuan_data = filtered_df.groupby('Ngành').agg({
        'Cá nhân Thỏa thuận Ròng': 'sum',
        'Nước ngoài Thỏa thuận Ròng': 'sum',
        'Tổ chức trong nước Thỏa thuận Ròng': 'sum',
        'Tự doanh Thỏa thuận Ròng': 'sum'
    }).reset_index()
    thoathuan_data['Tổng'] = thoathuan_data['Cá nhân Thỏa thuận Ròng'] + thoathuan_data['Nước ngoài Thỏa thuận Ròng'] + \
                             thoathuan_data['Tổ chức trong nước Thỏa thuận Ròng'] + thoathuan_data['Tự doanh Thỏa thuận Ròng']
    thoathuan_data = thoathuan_data.sort_values(by='Tổng', ascending=False)
    return pd.melt(
        thoathuan_data,
        id_vars=['Ngành'],
        value_vars=['Cá nhân Thỏa thuận Ròng', 'Nước ngoài Thỏa thuận Ròng', 'Tổ chức trong nước Thỏa thuận Ròng', 'Tự doanh Thỏa thuận Ròng'],
        var_name='Nhà đầu tư',
        value_name='Giá trị'
    )

# Hàm tạo biểu đồ cột chồng
def create_stacked_bar_chart(data, title, height=CHART_HEIGHT):
    """Tạo biểu đồ cột chồng."""
    fig = px.bar(
        data,
        x='Giá trị',
        y='Ngành',
        color='Nhà đầu tư',
        orientation='h',
        title=title,
        color_discrete_map=COLOR_MAP,
        template="plotly_white"  # Sử dụng theme plotly_white
    )
    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        barmode='stack',
        margin=dict(l=200),
        xaxis_title="Giá trị giao dịch (VND)",
        yaxis=dict(title="Số lượng", title_font=dict(size=14))
    )
    return fig


# Hàm chuẩn bị dữ liệu cho biểu đồ dòng tiền
def prepare_flow_chart_data(filtered_df):
    """Chuẩn bị dữ liệu cho biểu đồ thống kê dòng tiền."""
    flow_data = {
        'Cá nhân': filtered_df['Cá nhân Khớp Ròng'].sum() + filtered_df['Cá nhân Thỏa thuận Ròng'].sum(),
        'Tổ chức': filtered_df['Tổ chức trong nước Khớp Ròng'].sum() + filtered_df['Tổ chức trong nước Thỏa thuận Ròng'].sum(),
        'Tự doanh': filtered_df['Tự doanh Khớp Ròng'].sum() + filtered_df['Tự doanh Thỏa thuận Ròng'].sum(),
        'Nước ngoài': filtered_df['Nước ngoài Khớp Ròng'].sum() + filtered_df['Nước ngoài Thỏa thuận Ròng'].sum()
    }
    khop_data = {
        'Cá nhân': filtered_df['Cá nhân Khớp Ròng'].sum(),
        'Tổ chức': filtered_df['Tổ chức trong nước Khớp Ròng'].sum(),
        'Tự doanh': filtered_df['Tự doanh Khớp Ròng'].sum(),
        'Nước ngoài': filtered_df['Nước ngoài Khớp Ròng'].sum()
    }
    thoathuan_data = {
        'Cá nhân': filtered_df['Cá nhân Thỏa thuận Ròng'].sum(),
        'Tổ chức': filtered_df['Tổ chức trong nước Thỏa thuận Ròng'].sum(),
        'Tự doanh': filtered_df['Tự doanh Thỏa thuận Ròng'].sum(),
        'Nước ngoài': filtered_df['Nước ngoài Thỏa thuận Ròng'].sum()
    }
    return flow_data, khop_data, thoathuan_data

def create_flow_chart(flow_data, khop_data, thoathuan_data):
    """Tạo biểu đồ thống kê dòng tiền dạng Sankey với màu số trắng và hiệu ứng sóng."""
    investors = ['Cá nhân', 'Tổ chức', 'Tự doanh', 'Nước ngoài']
    fig = go.Figure()

    khop_values = [khop_data[investor] / 1e9 for investor in investors]
    thoathuan_values = [thoathuan_data[investor] / 1e9 for investor in investors]
    total_values = [(khop_data[investor] + thoathuan_data[investor]) / 1e9 for investor in investors]

    colors_light = 'rgba(52, 152, 219, 0.9)'
    colors_medium = 'rgba(41, 128, 185, 0.9)'
    colors_dark = 'rgba(23, 86, 162, 0.9)'

    fig.add_trace(go.Scatter(x=investors, y=khop_values, mode='none', name='Khớp', fill='tozeroy', fillcolor=colors_light,
                             hoverinfo='text', hovertext=[f'Khớp - {inv}: {val:.2f} tỷ' for inv, val in zip(investors, khop_values)]))
    fig.add_trace(go.Scatter(x=investors, y=thoathuan_values, mode='none', name='Thỏa thuận', fill='tozeroy', fillcolor=colors_medium,
                             hoverinfo='text', hovertext=[f'Thỏa thuận - {inv}: {val:.2f} tỷ' for inv, val in zip(investors, thoathuan_values)]))

    x_all, y_all, text_all = [], [], []
    for i in range(len(investors) - 1):
        for j in range(10):
            t = j / 10
            x_all.append(i + t)
            y_interp = total_values[i] * (1 - t) + total_values[i + 1] * t
            y_wave = y_interp + np.sin(t * np.pi) * min(total_values[i], total_values[i + 1]) * 0.05
            y_all.append(y_wave)
            text_all.append('')
    for i in range(len(investors)):
        x_all.append(i)
        y_all.append(total_values[i])
        text_all.append(f"{total_values[i]:.2f} tỷ")

    fig.add_trace(go.Scatter(
        x=[investors[i] for i in range(len(investors))],
        y=total_values,
        mode='lines+markers+text',
        line=dict(color=colors_dark, width=3, shape='spline', smoothing=1.3),
        marker=dict(size=8, color=colors_dark),
        text=[f"{val:.2f}bn" for val in total_values],
        textposition="top center",
        textfont=dict(color="black", size=14, weight='bold'),  # Màu chữ đen
        showlegend=False
    ))

    fig.update_layout(
        title=dict(text='Thống kê dòng tiền', font=dict(size=20)),
        xaxis=dict(title=dict(text='', font=dict(size=14))),
        yaxis=dict(title=dict(text='Giá trị (tỷ VND)', font=dict(size=14))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        plot_bgcolor='white',  # Màu nền của biểu đồ
        paper_bgcolor='white',  # Màu nền của giấy
        font=dict(color='black'),  # Màu chữ
        template="plotly_white"  # Sử dụng theme plotly_white
    )
    fig.update_traces(line=dict(shape='spline', smoothing=1.3))
    fig.update_xaxes(showgrid=False, showline=False, zeroline=False, tickfont=dict(size=14, color='black'))
    fig.update_yaxes(showgrid=False, showline=False, zeroline=False, tickfont=dict(size=12, color='black'))
    return fig

# Hàm hiển thị thống kê tổng quan
def show_overview_statistics(filtered_df):
    """Hiển thị thống kê tổng quan."""
    st.subheader("Thống kê tổng quát")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Tổng số ngành", filtered_df['Ngành'].nunique())
    with col2:
        total_value_canhan = filtered_df['Cá nhân Khớp Ròng'].sum() + filtered_df['Cá nhân Thỏa thuận Ròng'].sum()
        st.metric("Tổng Cá nhân Ròng", f"{total_value_canhan:,.0f} VND")
    with col3:
        total_value_nuocngoai = filtered_df['Nước ngoài Khớp Ròng'].sum() + filtered_df['Nước ngoài Thỏa thuận Ròng'].sum()
        st.metric("Tổng Nước ngoài Ròng", f"{total_value_nuocngoai:,.0f} VND")
    with col4:
        total_value_tochuc = filtered_df['Tổ chức trong nước Khớp Ròng'].sum() + filtered_df['Tổ chức trong nước Thỏa thuận Ròng'].sum()
        st.metric("Tổng Tổ chức Ròng", f"{total_value_tochuc:,.0f} VND")
    with col5:
        total_value_tudoanh = filtered_df['Tự doanh Khớp Ròng'].sum() + filtered_df['Tự doanh Thỏa thuận Ròng'].sum()
        st.metric("Tổng Tự doanh Ròng", f"{total_value_tudoanh:,.0f} VND")

# Hàm chuẩn bị dữ liệu thời gian
def prepare_time_series_data(filtered_df, column):
    """Chuẩn bị dữ liệu time series cho biểu đồ giao dịch theo thời gian."""
    daily_data = filtered_df.groupby('Date')[column].sum().reset_index()
    daily_data = daily_data.sort_values('Date')
    daily_data['Tích lũy ròng'] = daily_data[column].cumsum()
    daily_data['Ngày'] = daily_data['Date'].dt.strftime('%d/%m/%y')
    return daily_data

# Hàm tạo biểu đồ thời gian
def create_time_series_chart(daily_data, column, title):
    """Tạo biểu đồ cột và đường kết hợp cho giao dịch theo thời gian."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily_data['Ngày'], y=daily_data[column], name='Giao dịch ròng', marker_color='#1f77b4'))
    fig.add_trace(go.Scatter(x=daily_data['Ngày'], y=daily_data['Tích lũy ròng'], name='Tích lũy ròng', mode='lines+markers',
                             marker=dict(color='darkblue'), line=dict(color='darkblue', width=2), yaxis='y2'))
    fig.update_layout(
        title=dict(text=title, font=dict(size=20)),
        xaxis=dict(title=dict(text='Ngày', font=dict(size=14))),
        yaxis=dict(title=dict(text='Giao dịch ròng (VND)', font=dict(color='#1f77b4', size=14)),
                   tickfont=dict(color='#1f77b4')),
        yaxis2=dict(title=dict(text='Tích lũy ròng (VND)', font=dict(color='darkblue', size=14)),
                    tickfont=dict(color='darkblue'), anchor='x', overlaying='y', side='right'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        template="plotly_white"  # Sử dụng theme plotly_white
    )
    fig.add_shape(type="line", x0=daily_data['Ngày'].iloc[0], y0=0, x1=daily_data['Ngày'].iloc[-1], y1=0,
                  line=dict(color="gray", width=1, dash="dash"))
    return fig

# Hàm lấy tên cột
def get_column_name(group_option, chart_option):
    """Lấy tên cột dữ liệu phù hợp với nhóm và loại biểu đồ."""
    if group_option == "Cá nhân":
        return 'Cá nhân Khớp Ròng' if chart_option == "Khớp" else 'Cá nhân Thỏa thuận Ròng'
    elif group_option == "Nước ngoài":
        return 'Nước ngoài Khớp Ròng' if chart_option == "Khớp" else 'Nước ngoài Thỏa thuận Ròng'
    elif group_option == "Tổ chức":
        return 'Tổ chức trong nước Khớp Ròng' if chart_option == "Khớp" else 'Tổ chức trong nước Thỏa thuận Ròng'
    else:  # "Tự doanh"
        return 'Tự doanh Khớp Ròng' if chart_option == "Khớp" else 'Tự doanh Thỏa thuận Ròng'

# Hàm hiển thị biểu đồ chi tiết
def display_detail_chart(filtered_df, column, group_option, chart_option):
    """Hiển thị biểu đồ chi tiết theo nhóm và loại biểu đồ."""
    df_grouped = filtered_df.groupby('Ngành')[column].sum().reset_index()
    df_grouped = df_grouped.sort_values(by=column)
    chart_title = f'Giao dịch theo Ngành và {group_option} ({chart_option})'
    fig = px.bar(
        df_grouped,
        x=column,
        y='Ngành',
        color='Ngành',
        title=chart_title,
        labels={column: f'{group_option} ({chart_option}) (VND)', 'Ngành': 'Ngành'},
        template="plotly_white"  # Sử dụng theme plotly_white
    )
    st.plotly_chart(fig, use_container_width=True)
    if st.checkbox("Hiển thị dữ liệu thô"):
        st.subheader("Dữ liệu gốc")
        st.dataframe(filtered_df)
    st.subheader("Thống kê tổng quát")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tổng số ngành", filtered_df['Ngành'].nunique())
    with col2:
        if not filtered_df.empty:
            total_value = filtered_df[column].sum()
            st.metric(f"Tổng {group_option} ({chart_option}) Ròng", f"{total_value:,.0f} VND")
    return fig

# Hàm hiển thị trang Tổng quan
def show_overview_page(df):
    """Hiển thị trang tổng quan."""
    st.title("TỔNG QUAN GIAO DỊCH THEO NGÀNH VÀ NHÀ ĐẦU TƯ")

    # Bộ chọn thời gian
    st.sidebar.header("Chọn khoảng thời gian")
    min_date = df['Date'].min().date()
    max_date = df['Date'].max().date()
    start_date = st.sidebar.date_input("Ngày bắt đầu", min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input("Ngày kết thúc", max_date, min_value=min_date, max_value=max_date)

    # Lọc dữ liệu theo ngày giao dịch (không cache kết quả lọc)
    filtered_df = filter_data_by_date(df, start_date, end_date)

    if filtered_df.empty:
        st.warning("Không có dữ liệu nào trong khoảng thời gian đã chọn.")
        return

    # Danh sách chứa tất cả các biểu đồ để xuất PDF
    charts_for_pdf = {}

    # Chuẩn bị dữ liệu cho các biểu đồ
    khop_data_melted = prepare_khop_data(filtered_df)
    thoathuan_data_melted = prepare_thoathuan_data(filtered_df)

    # Hiển thị biểu đồ khớp
    st.subheader("Giao dịch Khớp Ròng theo ngành và nhà đầu tư")
    fig_khop = create_stacked_bar_chart(
        khop_data_melted,
        'Giao dịch Khớp lệnh ròng theo Ngành và Nhà đầu tư'
    )
    st.plotly_chart(fig_khop, use_container_width=True)
    charts_for_pdf['chart_khop'] = fig_khop

    # Hiển thị biểu đồ thỏa thuận
    st.subheader("Giao dịch Thỏa thuận Ròng theo ngành và nhà đầu tư")
    fig_thoathuan = create_stacked_bar_chart(
        thoathuan_data_melted,
        'Giao dịch Thỏa thuận ròng theo Ngành và Nhà đầu tư'
    )
    st.plotly_chart(fig_thoathuan, use_container_width=True)
    charts_for_pdf['chart_thoathuan'] = fig_thoathuan

    # Thêm biểu đồ thống kê dòng tiền
    st.subheader("Thống kê dòng tiền theo nhà đầu tư")
    flow_data, khop_data, thoathuan_data = prepare_flow_chart_data(filtered_df)
    fig_flow = create_flow_chart(flow_data, khop_data, thoathuan_data)
    st.plotly_chart(fig_flow, use_container_width=True)
    charts_for_pdf['chart_flow'] = fig_flow

    # Hiển thị thống kê tổng quan
    show_overview_statistics(filtered_df)

    # Nút xuất PDF cho trang tổng quan
    if st.sidebar.button("Export Selected Charts to PDF"):
        pdf_output = export_charts_to_pdf(charts_for_pdf)
        st.download_button(
            label="Download PDF",
            data=pdf_output,
            file_name="overview_charts.pdf",
            mime="application/pdf"
        )

# Hàm hiển thị trang Chi tiết
def show_detail_page(df):
    """Hiển thị trang chi tiết."""
    st.title("CHI TIẾT GIAO DỊCH THEO NGÀNH VÀ NHÀ ĐẦU TƯ")

    # Tạo thanh bên để chọn khoảng thời gian và loại nhóm
    st.sidebar.header("Chọn khoảng thời gian và Nhóm Giao Dịch")

    # Lấy ngày tối thiểu và tối đa từ dữ liệu
    min_date = df['Date'].min().date()
    max_date = df['Date'].max().date()

    # Tạo bộ chọn khoảng thời gian trong thanh bên
    start_date = st.sidebar.date_input("Ngày bắt đầu", min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input("Ngày kết thúc", max_date, min_value=min_date, max_value=max_date)

    # Lựa chọn nhóm giao dịch và loại biểu đồ
    group_option = st.sidebar.selectbox("Chọn nhóm giao dịch", ("Cá nhân", "Nước ngoài", "Tổ chức", "Tự doanh"))
    chart_option = st.sidebar.radio("Chọn loại biểu đồ", ("Khớp", "Thỏa thuận"))

    # Lọc dữ liệu theo ngày giao dịch (không cache kết quả lọc)
    filtered_df = filter_data_by_date(df, start_date, end_date)

    if filtered_df.empty:
        st.warning("Không có dữ liệu nào trong khoảng thời gian đã chọn.")
        return

    # Danh sách chứa tất cả các biểu đồ để xuất PDF
    detail_charts_for_pdf = {}

    # Chọn cột tương ứng với nhóm giao dịch và loại biểu đồ
    column = get_column_name(group_option, chart_option)

    # Xử lý và hiển thị dữ liệu chi tiết
    fig_detail = display_detail_chart(filtered_df, column, group_option, chart_option)
    detail_charts_for_pdf['chart_detail'] = fig_detail

    # Hiển thị biểu đồ giao dịch theo thời gian
    daily_data = prepare_time_series_data(filtered_df, column)
    st.subheader(f"Giao dịch ròng {group_option} ({chart_option}) theo thời gian và tích lũy ròng")
    fig_time_series = create_time_series_chart(
        daily_data,
        column,
        f'Giao dịch {group_option} ({chart_option}) ròng theo thời gian'
    )
    st.plotly_chart(fig_time_series, use_container_width=True)
    detail_charts_for_pdf['chart_time_series'] = fig_time_series

    # Nút xuất PDF cho trang chi tiết
    if st.sidebar.button("Export Selected Charts to PDF"):
        with tempfile.TemporaryDirectory() as tmpdirname:
            image_paths = []
            for name, fig in detail_charts_for_pdf.items():
                img_path = os.path.join(tmpdirname, f"{name}.png")
                fig.write_image(img_path, format="png")
                image_paths.append(img_path)
            pdf = FPDF()
            for img_path in image_paths:
                pdf.add_page()
                pdf.image(img_path, x=10, y=10, w=pdf.w - 20)
            pdf_output = pdf.output(dest="S").encode("latin1")
            st.download_button(
                label="Download PDF",
                data=pdf_output,
                file_name="detail_charts.pdf",
                mime="application/pdf"
            )
    
# Hàm hiển thị trang Market
def show_market_page(df_trade, df_marketcap, df_price):
    """Hiển thị trang Market với các biểu đồ giao dịch và kỹ thuật."""
    st.title("Thị trường Giao dịch")

    # Sidebar: Chọn khoảng thời gian
    st.sidebar.header("Chọn khoảng thời gian")
    min_date = min(df_trade['Date'].min().date(), df_marketcap['Date'].min().date(), df_price['Date'].min().date())
    max_date = max(df_trade['Date'].max().date(), df_marketcap['Date'].max().date(), df_price['Date'].max().date())
    start_date = st.sidebar.date_input("Ngày bắt đầu", min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input("Ngày kết thúc", max_date, min_value=min_date, max_value=max_date)
    if start_date > end_date:
        st.sidebar.error("Ngày bắt đầu không được lớn hơn ngày kết thúc!")
        st.stop()

    # Lọc dữ liệu theo ngày (không cache kết quả lọc)
    filtered_df_trade = filter_data_by_date(df_trade, start_date, end_date)
    filtered_df_marketcap = filter_data_by_date(df_marketcap, start_date, end_date)
    filtered_df_price = filter_data_by_date(df_price, start_date, end_date)

    if filtered_df_trade.empty or filtered_df_marketcap.empty or filtered_df_price.empty:
        st.warning("Không có dữ liệu nào trong khoảng thời gian đã chọn.")
        return

    # Sidebar: Chọn các biểu đồ muốn hiển thị
    st.sidebar.header("Chọn biểu đồ")
    show_chart1 = st.sidebar.checkbox("GTGD(B) & % thay đổi theo ngày", value=True)
    show_chart2 = st.sidebar.checkbox("Top 15 cổ phiếu (ngày mới nhất)", value=True)
    show_chart3 = st.sidebar.checkbox("Top 6 ngành (ngày mới nhất)", value=True)
    show_chart4 = st.sidebar.checkbox("Bubble Chart theo nhóm ngành", value=True)
    show_chart5 = st.sidebar.checkbox("Sức mạnh ngành theo thời gian", value=True)
    show_chart6 = st.sidebar.checkbox("Top 10 cổ phiếu theo vốn hóa (ngày mới nhất)", value=True)
    show_chart7 = st.sidebar.checkbox("Tỷ trọng vốn hóa theo ngành (ngày mới nhất)", value=True)
    show_chart8 = st.sidebar.checkbox("Xu hướng vốn hóa thị trường theo thời gian", value=True)
    show_chart9 = st.sidebar.checkbox("Số lượng cổ phiếu theo ngành có MACD tăng", value=True)
    show_chart10 = st.sidebar.checkbox("Số lượng cổ phiếu theo ngành có MA200 tăng", value=True)
    show_chart11 = st.sidebar.checkbox("Top 10 cổ phiếu có MACD tăng", value=True)
    show_chart12 = st.sidebar.checkbox("Top 10 cổ phiếu có MA200 tăng", value=True)

    # Dictionary lưu lại các biểu đồ để xuất PDF sau
    charts = {}

    # Hàm tính MACD và MA200
    def calculate_technicals(df_price, code):
        df_code = df_price[df_price['Code'] == code].sort_values('Date')
        if len(df_code) < 200:  # Đảm bảo đủ dữ liệu cho MA200
            return None, None
        
        # Tính EMA12, EMA26 và MACD
        df_code['EMA12'] = df_code['Close'].ewm(span=12, adjust=False).mean()
        df_code['EMA26'] = df_code['Close'].ewm(span=26, adjust=False).mean()
        df_code['MACD'] = df_code['EMA12'] - df_code['EMA26']
        df_code['Signal'] = df_code['MACD'].ewm(span=9, adjust=False).mean()
        df_code['MACD_Increasing'] = (df_code['MACD'] > df_code['Signal']) & (df_code['MACD'].shift(1) <= df_code['Signal'].shift(1))
        
        # Tính MA200
        df_code['MA200'] = df_code['Close'].rolling(window=200).mean()
        df_code['MA200_Increasing'] = (df_code['Close'] > df_code['MA200']) & (df_code['Close'].shift(1) <= df_code['MA200'].shift(1))
        
        return df_code['MACD_Increasing'].iloc[-1], df_code['MA200_Increasing'].iloc[-1]

    # Tính toán MACD và MA200 cho từng cổ phiếu
    latest_date = filtered_df_price['Date'].max()
    codes = filtered_df_price['Code'].unique()
    macd_increasing = []
    ma200_increasing = []
    for code in codes:
        macd_inc, ma200_inc = calculate_technicals(filtered_df_price, code)
        if macd_inc is not None and ma200_inc is not None:
            macd_increasing.append({'Code': code, 'MACD_Increasing': macd_inc})
            ma200_increasing.append({'Code': code, 'MA200_Increasing': ma200_inc})

    df_macd = pd.DataFrame(macd_increasing)
    df_ma200 = pd.DataFrame(ma200_increasing)

    # Kết hợp với thông tin ngành từ df_trade
    df_macd = pd.merge(df_macd, df_trade[['Code', 'Industry']].drop_duplicates(), on='Code', how='left')
    df_ma200 = pd.merge(df_ma200, df_trade[['Code', 'Industry']].drop_duplicates(), on='Code', how='left')

    # Tính số lượng cổ phiếu theo ngành có MACD và MA200 tăng
    macd_by_industry = df_macd[df_macd['MACD_Increasing']].groupby('Industry').size().reset_index(name='Count')
    ma200_by_industry = df_ma200[df_ma200['MA200_Increasing']].groupby('Industry').size().reset_index(name='Count')

    # Top 10 cổ phiếu có MACD và MA200 tăng (dựa trên giá trị giao dịch gần nhất)
    df_latest_trade = filtered_df_trade[filtered_df_trade['Date'] == latest_date]
    macd_top = pd.merge(df_macd[df_macd['MACD_Increasing']], df_latest_trade[['Code', 'TradeValue']], on='Code').nlargest(10, 'TradeValue')
    ma200_top = pd.merge(df_ma200[df_ma200['MA200_Increasing']], df_latest_trade[['Code', 'TradeValue']], on='Code').nlargest(10, 'TradeValue')

    ## Biểu đồ 1: GTGD(B) & % thay đổi theo ngày
    if show_chart1:
        st.markdown("### 1) Biểu đồ GTGD(B) & % thay đổi theo ngày")
        daily_value = filtered_df_trade.groupby('Date')['TradeValue'].sum().reset_index().sort_values('Date')
        daily_value['pct_change'] = daily_value['TradeValue'].pct_change() * 100
        daily_value['pct_change'].fillna(0, inplace=True)
        daily_value['Date_str'] = daily_value['Date'].dt.strftime('%Y-%m-%d')
        
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=daily_value['Date_str'], y=daily_value['TradeValue'], name="GTGD(B)", marker_color='skyblue'), secondary_y=False)
        fig1.add_trace(go.Scatter(x=daily_value['Date_str'], y=daily_value['pct_change'], name="% thay đổi", mode='lines+markers', marker_color='orange'), secondary_y=True)
        fig1.update_layout(
            title="GTGD(B) theo ngày & % thay đổi",
            template='plotly_white',
            hovermode="x unified",
            margin=dict(l=40, r=40, t=60, b=50)
        )
        fig1.update_xaxes(title_text="Ngày", type='category', categoryorder='category ascending')
        fig1.update_yaxes(title_text="GTGD(B) (tỷ đồng)", secondary_y=False)
        fig1.update_yaxes(title_text="% thay đổi", secondary_y=True)
        st.plotly_chart(fig1, use_container_width=True)
        charts['chart1'] = fig1

    ## Biểu đồ 2: Top 15 cổ phiếu (ngày mới nhất) với % thay đổi
    if show_chart2:
        st.markdown("### 2) Biểu đồ Top 15 cổ phiếu (ngày mới nhất) với % thay đổi")
        latest_date = filtered_df_trade['Date'].max()
        df_latest = filtered_df_trade[filtered_df_trade['Date'] == latest_date]
        code_latest = df_latest.groupby('Code', as_index=False)['TradeValue'].sum()
        def compute_pct_change(code):
            df_code = filtered_df_trade[filtered_df_trade['Code'] == code]
            df_prev = df_code[df_code['Date'] < latest_date]
            if df_prev.empty:
                return 0
            prev_date = df_prev['Date'].max()
            prev_value = df_prev[df_prev['Date'] == prev_date]['TradeValue'].sum()
            if prev_value == 0:
                return 0
            latest_value = code_latest.loc[code_latest['Code'] == code, 'TradeValue'].values[0]
            return (latest_value - prev_value) / prev_value * 100
        code_latest['pct_change'] = code_latest['Code'].apply(compute_pct_change)
        top_15 = code_latest.nlargest(15, 'TradeValue')
        fig2 = px.bar(
            top_15,
            x='Code',
            y='TradeValue',
            color='Code',
            text=top_15['pct_change'].apply(lambda x: f"{x:.2f}%"),
            title=f"Top 15 cổ phiếu (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig2.update_traces(textposition='outside')
        fig2.update_layout(
            xaxis_title="Mã cổ phiếu",
            yaxis_title="Giá trị giao dịch (tỷ đồng)",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig2, use_container_width=True)
        charts['chart2'] = fig2

    ## Biểu đồ 3: Top 6 ngành (ngày mới nhất) với % thay đổi
    if show_chart3:
        st.markdown("### 3) Biểu đồ Top 6 ngành (ngày mới nhất) với % thay đổi")
        latest_date = filtered_df_trade['Date'].max()
        df_latest = filtered_df_trade[filtered_df_trade['Date'] == latest_date]
        if 'Industry' in df_latest.columns:
            ind_latest = df_latest.groupby('Industry', as_index=False)['TradeValue'].sum()
            def compute_pct_change_ind(ind):
                df_ind = filtered_df_trade[filtered_df_trade['Industry'] == ind]
                df_prev = df_ind[df_ind['Date'] < latest_date]
                if df_prev.empty:
                    return 0
                prev_date = df_prev['Date'].max()
                prev_value = df_prev[df_prev['Date'] == prev_date]['TradeValue'].sum()
                if prev_value == 0:
                    return 0
                latest_value = ind_latest.loc[ind_latest['Industry'] == ind, 'TradeValue'].values[0]
                return (latest_value - prev_value) / prev_value * 100
            ind_latest['pct_change'] = ind_latest['Industry'].apply(compute_pct_change_ind)
            top_6 = ind_latest.nlargest(6, 'TradeValue')
            fig3 = px.bar(
                top_6,
                x='Industry',
                y='TradeValue',
                color='Industry',
                text=top_6['pct_change'].apply(lambda x: f"{x:.2f}%"),
                title=f"Top 6 ngành (ngày {latest_date.date()})",
                template='plotly_dark',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig3.update_traces(textposition='outside')
            fig3.update_layout(
                xaxis_title="Ngành",
                yaxis_title="Giá trị giao dịch (tỷ đồng)",
                margin=dict(l=80, r=50, t=70, b=50)
            )
            st.plotly_chart(fig3, use_container_width=True)
            charts['chart3'] = fig3
        else:
            st.warning("Không có cột 'Industry' để vẽ biểu đồ Top 6 ngành.")

    ## Biểu đồ 4: Bubble Chart theo nhóm ngành (chỉ Top 5 cổ phiếu/nhóm) với % thay đổi
    if show_chart4:
        st.markdown("### 4) Bubble Chart theo nhóm ngành (Top 5 cổ phiếu/nhóm) với % thay đổi")
        latest_date = filtered_df_trade['Date'].max()
        df_latest = filtered_df_trade[filtered_df_trade['Date'] == latest_date]
        if 'Industry' in df_latest.columns:
            df_ind_code = df_latest.groupby(['Industry', 'Code'], as_index=False)['TradeValue'].sum()
            def top_n_by_industry(group, n=5):
                return group.nlargest(n, 'TradeValue')
            df_top_by_ind = df_ind_code.groupby('Industry', group_keys=True).apply(top_n_by_industry, n=5)
            df_top_by_ind.reset_index(drop=True, inplace=True)
            
            def compute_pct_change(code):
                df_code = filtered_df_trade[filtered_df_trade['Code'] == code]
                df_prev = df_code[df_code['Date'] < latest_date]
                if df_prev.empty:
                    return 0
                prev_date = df_prev['Date'].max()
                prev_value = df_prev[df_prev['Date'] == prev_date]['TradeValue'].sum()
                latest_value = df_code[df_code['Date'] == latest_date]['TradeValue'].sum()
                if prev_value == 0:
                    return 0
                return (latest_value - prev_value) / prev_value * 100
            
            df_top_by_ind['pct_change'] = df_top_by_ind['Code'].apply(compute_pct_change)
            df_top_by_ind['ChangeStatus'] = np.where(df_top_by_ind['pct_change'] >= 0, 'Tăng', 'Giảm')
            
            unique_inds = df_top_by_ind['Industry'].unique()
            mapping = {ind: i for i, ind in enumerate(unique_inds)}
            df_top_by_ind['x'] = df_top_by_ind['Industry'].map(mapping) + np.random.rand(len(df_top_by_ind)) * 0.8
            df_top_by_ind['y'] = np.random.rand(len(df_top_by_ind)) * 10
            
            fig4 = px.scatter(
                df_top_by_ind,
                x='x', y='y',
                size='TradeValue',
                color='ChangeStatus',
                color_discrete_map={'Tăng': 'green', 'Giảm': 'red'},
                hover_name='Code',
                hover_data={'TradeValue': True, 'Industry': True, 'pct_change': ':.2f'},
                size_max=60,
                template='plotly_dark',
                title=f"Bubble Chart ngành (ngày {latest_date.date()}) - Top 5 cổ phiếu/nhóm"
            )
            fig4.update_layout(
                xaxis={'visible': False},
                yaxis={'visible': False},
                margin=dict(l=10, r=10, t=70, b=10)
            )
            st.plotly_chart(fig4, use_container_width=True)
            charts['chart4'] = fig4
        else:
            st.warning("Không có cột 'Industry' để vẽ Bubble Chart ngành.")

    ## Biểu đồ 5: Sức mạnh ngành theo thời gian (line chart)
    if show_chart5:
        st.markdown("### 5) Biểu đồ sức mạnh ngành theo thời gian")
        if 'Industry' not in filtered_df_trade.columns:
            st.warning("Không có cột 'Industry' để vẽ biểu đồ sức mạnh ngành.")
        else:
            df_industry_daily = filtered_df_trade.groupby(['Date', 'Industry'], as_index=False)['TradeValue'].sum()
            df_total_daily = filtered_df_trade.groupby('Date', as_index=False)['TradeValue'].sum()
            df_total_daily.rename(columns={'TradeValue': 'TotalValue'}, inplace=True)
            df_industry_daily = pd.merge(df_industry_daily, df_total_daily, on='Date', how='left')
            df_industry_daily['Share'] = df_industry_daily['TradeValue'] / df_industry_daily['TotalValue']
            pivot_share = df_industry_daily.pivot(index='Date', columns='Industry', values='Share').fillna(0)
            pivot_share.index = pivot_share.index.strftime('%Y-%m-%d')
            
            fig5 = px.line(
                pivot_share,
                x=pivot_share.index,
                y=pivot_share.columns,
                title="Sức mạnh ngành theo thời gian",
                template="plotly_dark"
            )
            fig5.update_layout(
                xaxis_title="Ngày",
                yaxis_title="Thị phần (%)",
                legend_title="Ngành",
                margin=dict(l=60, r=40, t=70, b=50)
            )
            st.plotly_chart(fig5, use_container_width=True)
            charts['chart5'] = fig5

    ## Biểu đồ 6: Top 10 cổ phiếu theo vốn hóa (ngày mới nhất)
    if show_chart6:
        st.markdown("### 6) Top 10 cổ phiếu theo vốn hóa (ngày mới nhất)")
        latest_date = filtered_df_marketcap['Date'].max()
        df_latest = filtered_df_marketcap[filtered_df_marketcap['Date'] == latest_date]
        top_10 = df_latest.groupby('Code', as_index=False)['MarketCap'].sum().nlargest(10, 'MarketCap')
        fig6 = px.bar(
            top_10,
            x='Code',
            y='MarketCap',
            color='Code',
            text=top_10['MarketCap'].apply(lambda x: f"{x:.2f}"),
            title=f"Top 10 cổ phiếu theo vốn hóa (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig6.update_traces(textposition='outside')
        fig6.update_layout(
            xaxis_title="Mã cổ phiếu",
            yaxis_title="Vốn hóa thị trường (tỷ đồng)",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig6, use_container_width=True)
        charts['chart6'] = fig6

    ## Biểu đồ 7: Tỷ trọng vốn hóa theo ngành (ngày mới nhất)
    if show_chart7:
        st.markdown("### 7) Tỷ trọng vốn hóa theo ngành (ngày mới nhất)")
        latest_date = filtered_df_marketcap['Date'].max()
        df_latest = filtered_df_marketcap[filtered_df_marketcap['Date'] == latest_date]
        if 'Industry' in df_latest.columns:
            industry_marketcap = df_latest.groupby('Industry', as_index=False)['MarketCap'].sum()
            fig7 = px.pie(
                industry_marketcap,
                values='MarketCap',
                names='Industry',
                title=f"Tỷ trọng vốn hóa theo ngành (ngày {latest_date.date()})",
                template='plotly_dark',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig7.update_traces(textinfo='percent+label')
            fig7.update_layout(margin=dict(l=50, r=50, t=70, b=50))
            st.plotly_chart(fig7, use_container_width=True)
            charts['chart7'] = fig7
        else:
            st.warning("Không có cột 'Industry' để vẽ biểu đồ tỷ trọng vốn hóa ngành.")

    ## Biểu đồ 8: Xu hướng vốn hóa thị trường theo thời gian
    if show_chart8:
        st.markdown("### 8) Xu hướng vốn hóa thị trường theo thời gian")
        daily_marketcap = filtered_df_marketcap.groupby('Date', as_index=False)['MarketCap'].sum()
        daily_marketcap['Date_str'] = daily_marketcap['Date'].dt.strftime('%Y-%m-%d')
        fig8 = px.line(
            daily_marketcap,
            x='Date_str',
            y='MarketCap',
            title="Xu hướng vốn hóa thị trường theo thời gian",
            template='plotly_dark'
        )
        fig8.update_layout(
            xaxis_title="Ngày",
            yaxis_title="Vốn hóa thị trường (tỷ đồng)",
            margin=dict(l=60, r=40, t=70, b=50)
        )
        st.plotly_chart(fig8, use_container_width=True)
        charts['chart8'] = fig8

    ## Biểu đồ 9: Số lượng cổ phiếu theo ngành có MACD tăng
    if show_chart9:
        st.markdown("### 9) Số lượng cổ phiếu theo ngành có MACD tăng")
        fig9 = px.bar(
            macd_by_industry,
            x='Industry',
            y='Count',
            color='Industry',
            text=macd_by_industry['Count'],
            title=f"Số lượng cổ phiếu có MACD tăng theo ngành (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig9.update_traces(textposition='outside')
        fig9.update_layout(
            xaxis_title="Ngành",
            yaxis_title="Số lượng cổ phiếu",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig9, use_container_width=True)
        charts['chart9'] = fig9

    ## Biểu đồ 10: Số lượng cổ phiếu theo ngành có MA200 tăng
    if show_chart10:
        st.markdown("### 10) Số lượng cổ phiếu theo ngành có MA200 tăng")
        fig10 = px.bar(
            ma200_by_industry,
            x='Industry',
            y='Count',
            color='Industry',
            text=ma200_by_industry['Count'],
            title=f"Số lượng cổ phiếu có MA200 tăng theo ngành (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig10.update_traces(textposition='outside')
        fig10.update_layout(
            xaxis_title="Ngành",
            yaxis_title="Số lượng cổ phiếu",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig10, use_container_width=True)
        charts['chart10'] = fig10

    ## Biểu đồ 11: Top 10 cổ phiếu có MACD tăng
    if show_chart11:
        st.markdown("### 11) Top 10 cổ phiếu có MACD tăng")
        fig11 = px.bar(
            macd_top,
            x='Code',
            y='TradeValue',
            color='Code',
            text=macd_top['TradeValue'].apply(lambda x: f"{x:.2f}"),
            title=f"Top 10 cổ phiếu có MACD tăng (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig11.update_traces(textposition='outside')
        fig11.update_layout(
            xaxis_title="Mã cổ phiếu",
            yaxis_title="Giá trị giao dịch (tỷ đồng)",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig11, use_container_width=True)
        charts['chart11'] = fig11

    ## Biểu đồ 12: Top 10 cổ phiếu có MA200 tăng
    if show_chart12:
        st.markdown("### 12) Top 10 cổ phiếu có MA200 tăng")
        fig12 = px.bar(
            ma200_top,
            x='Code',
            y='TradeValue',
            color='Code',
            text=ma200_top['TradeValue'].apply(lambda x: f"{x:.2f}"),
            title=f"Top 10 cổ phiếu có MA200 tăng (ngày {latest_date.date()})",
            template='plotly_dark',
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig12.update_traces(textposition='outside')
        fig12.update_layout(
            xaxis_title="Mã cổ phiếu",
            yaxis_title="Giá trị giao dịch (tỷ đồng)",
            margin=dict(l=80, r=50, t=70, b=50)
        )
        st.plotly_chart(fig12, use_container_width=True)
        charts['chart12'] = fig12


    # Nút xuất PDF cho trang Market
    if st.sidebar.button("Export Selected Charts to PDF"):
        with tempfile.TemporaryDirectory() as tmpdirname:
            image_paths = []
            for name, fig in charts.items():
                img_path = os.path.join(tmpdirname, f"{name}.png")
                fig.write_image(img_path, format="png")
                image_paths.append(img_path)
            pdf = FPDF()
            for img_path in image_paths:
                pdf.add_page()
                pdf.image(img_path, x=10, y=10, w=pdf.w - 20)
            pdf_output = pdf.output(dest="S").encode("latin1")
            st.download_button(
                label="Download PDF",
                data=pdf_output,
                file_name="market_charts.pdf",
                mime="application/pdf"
            )

def main():
    """Hàm chính của ứng dụng."""
    st.sidebar.title("Điều hướng")
    page = st.sidebar.radio("Chọn trang:", ("Tổng quan", "Chi tiết", "Market"))

def main():
    """Hàm chính của ứng dụng."""
    st.sidebar.title("Điều hướng")
    page = st.sidebar.radio("Chọn trang:", ("Tổng quan", "Chi tiết", "Market"))

    # Tải dữ liệu
    df = load_data()
    df_trade, df_marketcap, df_price = load_and_prepare_data(VOLUME_PATH, PRICE_PATH, SECTOR_PATH, MARKETCAP_PATH)
     # Thêm dòng này để tải df_price

    # Hiển thị trang tương ứng
    if page == "Tổng quan":
        show_overview_page(df)
    elif page == "Chi tiết":
        show_detail_page(df)
    else:  # page == "Market"
        show_market_page(df_trade, df_marketcap, df_price)  # Truyền thêm df_price

if __name__ == "__main__":
    main()