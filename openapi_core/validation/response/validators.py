"""OpenAPI core validation response validators module"""
import warnings

from openapi_core.casting.schemas.exceptions import CastError
from openapi_core.deserializing.exceptions import DeserializeError
from openapi_core.exceptions import MissingHeader
from openapi_core.exceptions import MissingRequiredHeader
from openapi_core.exceptions import MissingResponseContent
from openapi_core.templating.media_types.exceptions import MediaTypeFinderError
from openapi_core.templating.paths.exceptions import PathError
from openapi_core.templating.responses.exceptions import ResponseFinderError
from openapi_core.unmarshalling.schemas.enums import UnmarshalContext
from openapi_core.unmarshalling.schemas.exceptions import UnmarshalError
from openapi_core.unmarshalling.schemas.exceptions import ValidateError
from openapi_core.unmarshalling.schemas.factories import (
    SchemaUnmarshallersFactory,
)
from openapi_core.validation.response.datatypes import ResponseValidationResult
from openapi_core.validation.response.exceptions import HeadersError
from openapi_core.validation.validators import BaseValidator


class BaseResponseValidator(BaseValidator):
    @property
    def schema_unmarshallers_factory(self):
        spec_resolver = (
            self.spec.accessor.dereferencer.resolver_manager.resolver
        )
        return SchemaUnmarshallersFactory(
            spec_resolver,
            self.format_checker,
            self.custom_formatters,
            context=UnmarshalContext.RESPONSE,
        )

    def _find_operation_response(self, request, response):
        _, operation, _, _, _ = self._find_path(
            request.method, request.full_url_pattern
        )
        return self._get_operation_response(operation, response)

    def _get_operation_response(self, operation, response):
        from openapi_core.templating.responses.finders import ResponseFinder

        finder = ResponseFinder(operation / "responses")
        return finder.find(str(response.status_code))

    def _get_data(self, response, operation_response):
        if "content" not in operation_response:
            return None

        media_type, mimetype = self._get_media_type(
            operation_response / "content", response.mimetype
        )
        raw_data = self._get_data_value(response)
        deserialised = self._deserialise_data(mimetype, raw_data)
        casted = self._cast(media_type, deserialised)

        if "schema" not in media_type:
            return casted

        schema = media_type / "schema"
        data = self._unmarshal(schema, casted)

        return data

    def _get_data_value(self, response):
        if not response.data:
            raise MissingResponseContent(response)

        return response.data

    def _get_headers(self, response, operation_response):
        if "headers" not in operation_response:
            return {}

        headers = operation_response / "headers"

        errors = []
        validated = {}
        for name, header in list(headers.items()):
            # ignore Content-Type header
            if name.lower() == "content-type":
                continue
            try:
                value = self._get_header(name, header, response)
            except MissingHeader:
                continue
            except (
                MissingRequiredHeader,
                DeserializeError,
                CastError,
                ValidateError,
                UnmarshalError,
            ) as exc:
                errors.append(exc)
                continue
            else:
                validated[name] = value

        if errors:
            raise HeadersError(context=errors, headers=validated)

        return validated

    def _get_header(self, name, header, response):
        deprecated = header.getkey("deprecated", False)
        if deprecated:
            warnings.warn(
                f"{name} header is deprecated",
                DeprecationWarning,
            )

        try:
            return self._get_param_or_header_value(
                header, response.headers, name=name
            )
        except KeyError:
            required = header.getkey("required", False)
            if required:
                raise MissingRequiredHeader(name)
            raise MissingHeader(name)


class ResponseDataValidator(BaseResponseValidator):
    def validate(self, request, response):
        try:
            operation_response = self._find_operation_response(
                request, response
            )
        # don't process if operation errors
        except (PathError, ResponseFinderError) as exc:
            return ResponseValidationResult(errors=[exc])

        try:
            data = self._get_data(response, operation_response)
        except (
            MediaTypeFinderError,
            MissingResponseContent,
            DeserializeError,
            CastError,
            ValidateError,
            UnmarshalError,
        ) as exc:
            data = None
            data_errors = [exc]
        else:
            data_errors = []

        return ResponseValidationResult(
            errors=data_errors,
            data=data,
        )


class ResponseHeadersValidator(BaseResponseValidator):
    def validate(self, request, response):
        try:
            operation_response = self._find_operation_response(
                request, response
            )
        # don't process if operation errors
        except (PathError, ResponseFinderError) as exc:
            return ResponseValidationResult(errors=[exc])

        try:
            headers = self._get_headers(response, operation_response)
        except HeadersError as exc:
            headers = exc.headers
            headers_errors = exc.context
        else:
            headers_errors = []

        return ResponseValidationResult(
            errors=headers_errors,
            headers=headers,
        )


class ResponseValidator(BaseResponseValidator):
    def validate(self, request, response):
        try:
            operation_response = self._find_operation_response(
                request, response
            )
        # don't process if operation errors
        except (PathError, ResponseFinderError) as exc:
            return ResponseValidationResult(errors=[exc])

        try:
            data = self._get_data(response, operation_response)
        except (
            MediaTypeFinderError,
            MissingResponseContent,
            DeserializeError,
            CastError,
            ValidateError,
            UnmarshalError,
        ) as exc:
            data = None
            data_errors = [exc]
        else:
            data_errors = []

        try:
            headers = self._get_headers(response, operation_response)
        except HeadersError as exc:
            headers = exc.headers
            headers_errors = exc.context
        else:
            headers_errors = []

        errors = data_errors + headers_errors
        return ResponseValidationResult(
            errors=errors,
            data=data,
            headers=headers,
        )
