import logging
import functions

# Logging for URL collection
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("collect_urls.log", encoding="utf-8")
    ]
)


def main():
    print("Starting URL collection...")
    logging.info("Starting URL collection run")
    functions.collect_urls()

    logging.info("URL collection finished")
    print("URL collection finished.")


if __name__ == "__main__":
    main()
