package service

import (
	"context"
	"io"
)

const (
	Name        = "WfmAgent"
	DisplayName = "WG Free Mesh Agent"
)

type Runner func(ctx context.Context, stderr io.Writer) error
