<div align="center">
    <h1>Hack the Back</h1>
</div>

<div align="center">
    <strong>An elegant backend for Hackathons</strong>
</div>

<div align="center">
    <em>A Hackathon event platform to elegantly handle Hacker apps, with ready-made GraphQL and REST endpoints.</em>
</div>

<br/>

<div align="center">
    <a href="./LICENSE">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
    </a>
    <a href="https://github.com/psf/black">
        <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black" />
    </a>
    <a href="https://www.python.org/downloads/release/python-380/">
        <img src="https://img.shields.io/badge/python-3.8-blue.svg" alt="Python 3.8" />
    </a>
</div>

## Table of Contents

-   [Installation](#Installation)
-   [Schema Documentation](#Schema-Documentation)
-   [Contributing](#Contributing)
-   [License](#License)

## Installation

Hack the Back requires [Python 3.8](https://www.python.org/downloads/release/python-386/), and [PostgreSQL](https://www.postgresql.org/) at minimum, to run in real-world production environments.

Please view production installation instructions on the [Wiki page](https://github.com/hackthevalley/hack-the-back/wiki/Installation).

## Schema Documentation

Hack the Back provides both GraphQL and REST APIs for use by the client.

### GraphQL Documentation

This project uses [Graphene](https://graphene-python.org/) with [Django Rest Framework](https://www.django-rest-framework.org) serializers in order to build the GraphQL API. Every GraphQL server has an introspection system and Graphene is no different. To view the schema from this system, the GraphQL playground is included:

-   **Playground:** [/api/graphql](http://localhost:8000/api/graphql)

#### Download the Schema via the CLI

```bash
./manage.py graphql_schema --schema tutorial.quickstart.schema --out schema.json
```

### REST Documentation

This project uses [drf-spectacular](https://github.com/tfranzel/drf-spectacular) to automatically generate an OpenAPI 3.0 schema for the REST API that is built with the [Django Rest Framework](https://www.django-rest-framework.org).

-   **Swagger UI:** [/api/swagger](http://localhost:8000/api/swagger)
-   **OpenAPI Schema** (yaml)**:** [/api/schema.yaml](http://localhost:8000/api/schema.yaml)
-   **OpenAPI Schema** (json)**:** [/api/schema.json](http://localhost:8000/api/schema.json)
-   **OpenAPI Schema** (via content negotiation)**:** [/api/schema](http://localhost:8000/api/schema)

#### Download the Schema via the CLI

```
./manage.py spectacular --file schema.yml
```

_**Fun fact:** You can take advantage of this project's OpenAPI 3.0 Schema to do [automatic code generation](https://openapi-generator.tech/) for the client or server. In other words, you can generate SDKs for a client library or framework — such as Angular. Alternatively, you can generate some starter code in another back-end web framework with the same REST endpoints._ :thinking:

## Contributing

Hack the Back requires contributors to install [Python 3.8](https://www.python.org/downloads/release/python-386/) and [Poetry](https://python-poetry.org/) at minimum, to run in a development environment. The database in the development environment uses the SQLite engine, which stores data in an SQLite file in the root directory.

Please view the [Contributing Wiki pages](https://github.com/hackthevalley/hack-the-back/wiki/How-to-Contribute) for more details on installation and best practices.

## License

Everything in this repository is under the [MIT License](./LICENSE). Please carefully read and comply with the [license](./LICENSE) agreement.

**Created with&nbsp;:heart:&nbsp;&nbsp;by [Hack the Valley](https://hackthevalley.io/).**

---

<p align="center">
<a target="_blank" rel="noreferrer noopener" href="https://hackthevalley.io">
  <img src="https://cdn.hackthevalley.io/assets/logo?color=gray" width="25"/>
</a>
</p>
