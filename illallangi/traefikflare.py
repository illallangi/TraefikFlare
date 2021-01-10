from os.path import basename
from sys import argv, stderr
from time import sleep

from CloudFlare import CloudFlare
from CloudFlare.exceptions import CloudFlareAPIError

from click import Choice as CHOICE, INT, STRING, command, option

from illallangi.ipify import IPIFY
from illallangi.traefik import Traefik

from loguru import logger

from notifiers.logging import NotificationHandler


@command()
@option(
    "--log-level",
    envvar="LOG_LEVEL",
    type=CHOICE(
        ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "SUCCESS", "TRACE"],
        case_sensitive=False,
    ),
    default="INFO",
)
@option("--slack-webhook", type=STRING, envvar="SLACK_WEBHOOK", default=None)
@option(
    "--slack-username", type=STRING, envvar="SLACK_USERNAME", default=basename(argv[0])
)
@option("--slack-format", type=STRING, envvar="SLACK_FORMAT", default="{message}")
@option("--sleep-time", type=INT, envvar="SLEEP_TIME", default=300)
@option(
    "--traefik-url", type=STRING, envvar="TRAEFIK_URL", default="http://traefik:8080"
)
@option("--ipify-url", type=STRING, envvar="IPIFY_URL", default="https://api.ipify.org")
@option("--cloudflare-email", type=STRING, envvar="CLOUDFLARE_EMAIL", required=True)
@option("--cloudflare-api-key", type=STRING, envvar="CLOUDFLARE_API_KEY", required=True)
def TraefikFlare(
    log_level,
    slack_webhook,
    slack_username,
    slack_format,
    sleep_time,
    traefik_url,
    ipify_url,
    cloudflare_email,
    cloudflare_api_key,
):
    logger.remove()
    logger.add(stderr, level=log_level)

    if slack_webhook:
        params = {"username": slack_username, "webhook_url": slack_webhook}
        slack = NotificationHandler("slack", defaults=params)
        logger.add(slack, format=slack_format, level="SUCCESS")

    logger.success(f"{basename(argv[0])} Started")
    logger.info(f'  --log-level "{log_level}"')
    logger.info(f'  --slack-webhook "{slack_webhook}"')
    logger.info(f'  --slack-username "{slack_username}"')
    logger.info(f'  --slack-format "{slack_format}"')
    logger.info(f"  --sleep-time {sleep_time}")
    logger.info(f'  --traefik-url "{traefik_url}"')
    logger.info(f'  --ipify-url "{ipify_url}"')
    logger.info(f'  --cloudflare-email "{cloudflare_email}"')
    logger.info(f'  --cloudflare-api-key "{cloudflare_api_key}"')

    traefik = Traefik(url=traefik_url)
    ipify = IPIFY(url=ipify_url)
    cloudflare = CloudFlare(email=cloudflare_email, token=cloudflare_api_key)

    zones = None
    while True:
        try:
            zones = {
                zone["name"]: zone["id"]
                for zone in cloudflare.zones.get(params={"per_page": 100})
            }
            logger.info(f"Cloudflare connection OK, {len(zones)} zones found:")
            for zone in zones:
                logger.info(f"  {zones[zone]}: {zone}")
        except CloudFlareAPIError as e:
            logger.error(
                f"CloudFlareAPIError getting zones for {cloudflare_email}: {e}"
            )
            continue
        except Exception as e:
            logger.error(f"Exception getting zones for {cloudflare_email}: {e}")
            continue
        if zones is not None:
            break
        logger.info(f"Sleeping {sleep_time} seconds")
        sleep(sleep_time)

    previous = None
    current = None

    while True:
        try:
            hosts = traefik.routes.hosts
            logger.info(f"Traefik connection OK, {hosts} hosts found:")
            for host in hosts:
                logger.info(f"  {host}")
        except Exception as e:
            logger.error(f"Exception getting hosts from {traefik_url}: {e}")
            previous = None
            logger.info(f"Sleeping {sleep_time} seconds")
            sleep(sleep_time)
            continue

        try:
            ip_address = ipify.ip_address
        except Exception as e:
            logger.error(f"Exception getting IP address from {ipify_url}: {e}")
            previous = None
            logger.info(f"Sleeping {sleep_time} seconds")
            sleep(sleep_time)
            continue

        current = {
            host: str(ip_address) for host in hosts if host.endswith(tuple(zones))
        }

        if current != previous:
            logger.info(
                f"Hosts changed, {len(current)} hosts found ({len(hosts) - len(current)} filtered):"
            )
            previous = current
            for host in current:
                zone_name = [zone for zone in zones if host.endswith(zone)][0]
                zone_id = zones[zone_name]
                logger.debug(
                    f"Starting {host} {current[host]} in zone {zone_id} {zone_name}"
                )

                try:
                    dns_records = cloudflare.zones.dns_records.get(
                        zone_id, params={"name": host, "match": "all", "type": "A"}
                    )
                except CloudFlareAPIError as e:
                    logger.error(
                        f"CloudFlareAPIError getting dns records for {zone_id}: {host}: {e}"
                    )
                    previous = None
                    continue
                except Exception as e:
                    logger.error(
                        f"Exception getting dns records for {zone_id}: {host}: {e}"
                    )
                    previous = None
                    continue
                if len(dns_records) > 1:
                    logger.error(
                        f"Received {len(dns_records)} dns records for {zone_id}: {host}, expected 1"
                    )
                    previous = None
                    continue

                if len(dns_records) == 0:
                    # Create a new record
                    try:
                        cloudflare.zones.dns_records.post(
                            zone_id,
                            data={
                                "name": host,
                                "type": "A",
                                "content": current[host],
                                "proxied": False,
                            },
                        )
                    except CloudFlareAPIError as e:
                        logger.error(
                            f"CloudFlareAPIError creating dns record for {zone_id}: {host}: {e}"
                        )
                        previous = None
                        continue
                    except Exception as e:
                        logger.error(
                            f"Exception creating dns record for {zone_id}: {host}: {e}"
                        )
                        previous = None
                        continue
                    logger.success(f"{host} created and set to {current[host]}.")

                if len(dns_records) == 1:
                    # update the record - unless it's already correct
                    dns_record = dns_records[0]
                    old_ip_address = dns_record["content"]

                    if current[host] == old_ip_address:
                        logger.info(
                            f"{host} already set to {current[host]}, no change required."
                        )
                        continue

                    dns_record_id = dns_record["id"]
                    try:
                        cloudflare.zones.dns_records.put(
                            zone_id,
                            dns_record_id,
                            data={
                                "name": host,
                                "type": "A",
                                "content": current[host],
                                "proxied": False,
                            },
                        )
                    except CloudFlareAPIError as e:
                        logger.error(
                            f"CloudFlareAPIError updating dns record for {zone_id}: {host}: {e}"
                        )
                        previous = None
                        continue
                    except Exception as e:
                        logger.error(
                            f"Exception updating dns record for {zone_id}: {host}: {e}"
                        )
                        previous = None
                        continue
                    logger.success(
                        f"{host} updated from {old_ip_address} to {current[host]}."
                    )

        if sleep_time == 0:
            break

        logger.info(f"Sleeping {sleep_time} seconds")
        sleep(sleep_time)


if __name__ == "__main__":
    TraefikFlare()
