resource "aws_lb" "public" {
  name               = "${var.project}-public-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_public.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  tags = merge(local.common_tags, { Name = "public-alb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.project}-api-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check { path = "/health"; healthy_threshold = 3; unhealthy_threshold = 3; timeout = 5; interval = 30 }
  tags = merge(local.common_tags, { Service = "api" })
}

resource "aws_lb_target_group" "exporter" {
  name        = "${var.project}-exporter-tg"
  port        = 9090
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check { path = "/health"; healthy_threshold = 2; unhealthy_threshold = 3; timeout = 10; interval = 30 }
  tags = merge(local.common_tags, { Service = "data-exporter" })
}

resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.public.arn
  port              = 80
  protocol          = "HTTP"
  default_action { type = "forward"; target_group_arn = aws_lb_target_group.api.arn }
}

resource "aws_lb_listener_rule" "exporter_route" {
  listener_arn = aws_lb_listener.main.arn
  priority     = 100
  action { type = "forward"; target_group_arn = aws_lb_target_group.exporter.arn }
  condition { path_pattern { values = ["/api/v1/exports/*", "/api/v1/data-export/*"] } }
}
