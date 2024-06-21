import json
from dataclasses import is_dataclass

import pytest

from openapi_core.testing import MockRequest
from openapi_core.testing import MockResponse
from openapi_core.unmarshalling.request.unmarshallers import (
    V30RequestUnmarshaller,
)
from openapi_core.unmarshalling.response.unmarshallers import (
    V30ResponseUnmarshaller,
)
from openapi_core.validation.request.exceptions import InvalidRequestBody
from openapi_core.validation.response.exceptions import InvalidData


@pytest.fixture(scope="class")
def schema_path(schema_path_factory):
    return schema_path_factory.from_file("data/v3.0/split.yaml")


@pytest.fixture(scope="class")
def request_unmarshaller(schema_path):
    return V30RequestUnmarshaller(schema_path)


class TestReadOnly:
    def test_split_spec(self, request_unmarshaller):
        data = json.dumps(
            {
                "id": 10,
            }
        ).encode()

        request = MockRequest(
            host_url="", method="POST", path="/users", data=data
        )

        result = request_unmarshaller.unmarshal(request)

        assert len(result.errors) == 1
        assert type(result.errors[0]) == InvalidRequestBody
        assert result.body is None
