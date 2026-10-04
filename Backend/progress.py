from queue import Queue

progress_queue = Queue()

def update_progress(message):
    print("PROGRESS:", message) 
    progress_queue.put(message)