import argparse
import asyncio
import logging
import sys
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from scraper.engine import engine
from database import db
import config

console = Console()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_time=True)]
    )

async def main():
    parser = argparse.ArgumentParser(description="Flexnet Japan Vehicle Scraper CLI")
    parser.add_argument("--pages", type=int, default=None, help="Max search listing pages to crawl (100 cars/page)")
    parser.add_argument("--limit", type=int, default=None, help="Max vehicles to scrape")
    parser.add_argument("--workers", type=int, default=config.DEFAULT_CONCURRENCY, help="Number of concurrent workers")
    parser.add_argument("--incremental", action="store_true", help="Only scrape cars not currently in Supabase")
    parser.add_argument("--no-details", action="store_true", help="Only scrape search list without deep detail pages")
    parser.add_argument("--test", action="store_true", help="Quick test run (first 5 cars)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    console.print("\n[bold cyan]====================================================[/bold cyan]")
    console.print("[bold cyan]       FLEXNET JAPAN VEHICLE SCRAPER CLI           [/bold cyan]")
    console.print("[bold cyan]====================================================[/bold cyan]\n")

    # Check database connection
    db_stats = db.get_stats()
    if db_stats.get("connected"):
        console.print(f"[bold green]✔ Supabase Connected[/bold green] | Current Vehicles in DB: [bold]{db_stats.get('total_vehicles')}[/bold]")
    else:
        console.print("[bold yellow]⚠ Supabase not connected or table not created yet.[/bold yellow]")
        console.print("  Make sure to run [cyan]schema.sql[/cyan] in your Supabase SQL Editor if you haven't already.\n")

    max_pages = args.pages
    max_cars = args.limit
    if args.test:
        console.print("[bold magenta]Running in TEST mode (scraping first 5 cars)[/bold magenta]")
        max_pages = 1
        max_cars = 5

    engine.concurrency = args.workers

    console.print(f"Workers: [bold]{args.workers}[/bold] | Incremental: [bold]{args.incremental}[/bold] | Deep Details: [bold]{not args.no_details}[/bold]\n")

    try:
        result = await engine.run_scrape(
            max_pages=max_pages,
            max_cars=max_cars,
            scrape_details=not args.no_details,
            incremental=args.incremental
        )

        # Output Summary Table
        table = Table(title="Scraping Job Summary", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="green")

        table.add_row("Status", result.get("current_action", "Done"))
        table.add_row("Total Site Inventory", str(result.get("total_inventory_site", 0)))
        table.add_row("Vehicles Processed", str(result.get("scraped_count", 0)))
        table.add_row("New Vehicles Added", str(result.get("new_cars_count", 0)))
        table.add_row("Existing Updated", str(result.get("updated_count", 0)))
        table.add_row("Errors Encountered", str(result.get("errors_count", 0)))
        table.add_row("Elapsed Time", f"{result.get('elapsed_seconds', 0)} seconds")

        console.print("\n")
        console.print(table)
        console.print("\n[bold green]Job successfully completed.[/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelling scrape job...[/yellow]")
        engine.stop()
    except Exception as e:
        console.print(f"\n[bold red]Error running scraper:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
