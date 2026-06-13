from app.stream_reader import StreamReader


def test_set_url_updates_url_and_signals_reconnect():
    reader = StreamReader("rtsp://localhost:8554/cam1", name="cam1")

    reader.set_url("/uploads/cam1/clip.mp4")

    assert reader.url == "/uploads/cam1/clip.mp4"
    assert reader._url_changed.is_set()


def test_set_url_is_noop_for_same_url():
    reader = StreamReader("rtsp://localhost:8554/cam1", name="cam1")

    reader.set_url("rtsp://localhost:8554/cam1")

    assert not reader._url_changed.is_set()
