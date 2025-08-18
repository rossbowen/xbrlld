import click

from xbrlld.instance import write_instance_to_rdf
from xbrlld.taxonomy import write_taxonomy_to_rdf


@click.group()
def cli():
    """Convert XBRL taxonomies and instance documents to RDF."""
    pass


@cli.group()
def convert():
    """Convert XBRL files to RDF format."""
    pass


@convert.command()
@click.argument("taxonomy_path")
@click.option(
    "--output",
    "-o",
    default="taxonomy.ttl",
    help="Output file path (default: taxonomy.ttl)",
)
def taxonomy(taxonomy_path: str, output: str):
    """
    Convert an XBRL taxonomy document to RDF.

    TAXONOMY_PATH: Path or URL to the taxonomy document (local file or web resource).
    """
    try:

        write_taxonomy_to_rdf(taxonomy_path, output)
        click.echo(f"Converted taxonomy to {output}")
    except Exception as e:
        click.echo(str(e))
        import sys

        sys.exit(1)


@convert.command()
@click.argument("instance_path")
@click.option(
    "--output",
    "-o",
    default="facts.ttl",
    help="Output file path (default: facts.ttl)",
)
def instance(instance_path: str, output: str):
    """
    Convert an XBRL instance document to RDF.

    INSTANCE_PATH: Path or URL to the instance document (local file or web resource).
    """
    try:

        write_instance_to_rdf(instance_path, output)
        click.echo(f"Converted instance document to {output}")
    except Exception as e:
        click.echo(str(e))
        import sys

        sys.exit(1)
