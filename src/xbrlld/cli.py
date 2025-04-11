import click

from .converter import XBRLtoRDFConverter


@click.group()
def cli():
    """Convert XBRL taxonomies and instance documents to RDF."""
    pass


@cli.group()
def convert():
    """Convert XBRL files to RDF format."""
    pass


@convert.command()
@click.argument("taxonomy_url")
@click.option(
    "--output",
    "-o",
    default="taxonomy.trig",
    help="Output file path (default: taxonomy.trig)",
)
def taxonomy(taxonomy_url: str, output: str):
    """Convert an XBRL taxonomy to RDF.

    TAXONOMY_URL: URL or file path of the XBRL taxonomy
    """
    converter = XBRLtoRDFConverter()
    converter.convert_taxonomy(taxonomy_url, output)
    click.echo(f"Converted taxonomy to {output}")


@convert.command()
@click.argument("instance_file")
@click.option("--with-taxonomy", "-t", is_flag=True, help="Include taxonomy conversion")
@click.option(
    "--output",
    "-o",
    default="facts.trig",
    help="Output file path (default: facts.trig)",
)
def instance(instance_file: str, with_taxonomy: bool, output: str):
    """Convert an XBRL instance document to RDF.

    INSTANCE_FILE: Path to XBRL instance document
    """
    converter = XBRLtoRDFConverter()
    converter.convert_instance(instance_file, output)
    click.echo(f"Converted instance document to {output}")
